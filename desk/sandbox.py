"""Run standard-library Python in a fresh WASI guest for each request."""
import subprocess
import sys
import tempfile
from pathlib import Path

TIMEOUT_SECONDS = 10
RUNTIME = Path(__file__).resolve().parents[1] / "data" / "runtime" / "cpython-3.14.4-wasi"


class SandboxUnavailable(RuntimeError):
    pass


def run_sandboxed(code: str, files: dict[str, bytes] | None = None) -> tuple[bool, str]:
    if not (RUNTIME / "python.wasm").is_file():
        raise SandboxUnavailable("The local Python sandbox is missing. Run sh setup.sh before going offline.")
    with tempfile.TemporaryDirectory(prefix="desk-code-") as tmp:
        work = Path(tmp) / "work"
        work.mkdir()
        program = Path(tmp) / "program"
        program.mkdir()
        (program / "main.py").write_text(code, encoding="utf-8")
        for name, data in (files or {}).items():
            if Path(name).name != name or name in ("", ".", ".."):
                return False, "Invalid attachment filename."
            (work / name).write_bytes(data)
        with tempfile.TemporaryFile() as output:
            try:
                result = subprocess.run(
                    [sys.executable, "-I", str(Path(__file__).resolve()), str(work), str(program)],
                    stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
                    timeout=TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired:
                return False, f"Stopped after {TIMEOUT_SECONDS} seconds."
            output.seek(max(0, output.tell() - 8192))
            message = output.read().decode(errors="replace").strip()
            return result.returncode == 0, message[-4000:]


def _run_guest(work: str, program: str) -> int:
    import resource
    import wasmtime

    # Bound writes by the worker, including its captured stdout/stderr, at the OS level.
    resource.setrlimit(resource.RLIMIT_FSIZE, (1 << 20, 1 << 20))
    config = wasmtime.Config()
    config.consume_fuel = True
    engine = wasmtime.Engine(config)
    module = wasmtime.Module.from_file(engine, str(RUNTIME / "python.wasm"))
    store = wasmtime.Store(engine)
    store.set_limits(memory_size=128 << 20)
    store.set_fuel(12_000_000_000)
    wasi = wasmtime.WasiConfig()
    wasi.argv = ["python", "-B", "-s", "-S", "/program/main.py"]
    wasi.env = [("PYTHONHOME", "/runtime")]
    wasi.preopen_dir(str(RUNTIME / "lib"), "/runtime/lib", False)
    wasi.preopen_dir(program, "/program", False)
    wasi.preopen_dir(work, ".", True)
    wasi.inherit_stdout()
    wasi.inherit_stderr()
    store.set_wasi(wasi)
    linker = wasmtime.Linker(engine)
    linker.define_wasi()
    instance = linker.instantiate(store, module)
    try:
        instance.exports(store)["_start"](store)
    except wasmtime.ExitTrap as exit_status:
        return exit_status.code
    except wasmtime.Trap as error:
        print(f"Sandbox stopped the program: {error.message.splitlines()[-1]}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(_run_guest(*sys.argv[1:]))
