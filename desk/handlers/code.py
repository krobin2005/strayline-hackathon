"""Code: write Python from a prompt, then prove it works by running it in a sandbox.

Flow: Gemma 4 E4B writes the code plus a small self-test → we run it in a separate process
(no network, temporary folder, 10-second limit) → if it fails, the error goes back to the model
once for a fix → the user sees the code, the output and whether its tests passed.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .. import llm
from . import Answer

KIND = "code"
TIMEOUT_SECONDS = 10
PASS_MARKER = "ALL TESTS PASSED"

_CODE_REQUEST = re.compile(
    r"\b(write|create|generate|implement|code|build|make)\b.{0,60}\b(function|script|program|code|class|"
    r"regex|regular expression|parser|query|snippet|method)\b|\bin python\b|\bpython (function|script|code)\b",
    re.IGNORECASE | re.DOTALL,
)

SYSTEM = (
    "You write correct, simple Python 3 code. Reply with exactly one ```python code block and nothing "
    "else. Use only the standard library unless the user names a library. The block must contain:\n"
    "1. the code the user asked for;\n"
    "2. at the end, under `if __name__ == \"__main__\":`, a short self-test that calls it on 2-4 "
    "realistic examples, checks the results with `assert`, prints each result, and finally prints "
    f"exactly `{PASS_MARKER}`.\n"
    "Think about edge cases before writing. Do not read or write files unless asked; never use the network."
)

# macOS sandbox profile: allow normal execution but deny all network access.
_SANDBOX_PROFILE = "(version 1)(allow default)(deny network*)"


def is_code_request(question: str) -> bool:
    return bool(_CODE_REQUEST.search(question or ""))


def _extract_code(reply: str) -> str:
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", reply, re.DOTALL)
    return max(blocks, key=len).strip() if blocks else reply.strip()


def run_sandboxed(code: str, files: dict[str, bytes] | None = None) -> tuple[bool, str]:
    """Run code in a throwaway folder. Returns (finished without error, combined output)."""
    with tempfile.TemporaryDirectory(prefix="desk-run-") as tmp:
        script = Path(tmp) / "main.py"
        script.write_text(code)
        for name, data in (files or {}).items():
            (Path(tmp) / Path(name).name).write_bytes(data)
        command = [sys.executable, "-I", str(script)]
        if shutil.which("sandbox-exec"):
            command = ["sandbox-exec", "-p", _SANDBOX_PROFILE] + command
        env = {"PATH": "/usr/bin:/bin", "HOME": tmp, "PYTHONDONTWRITEBYTECODE": "1"}
        try:
            result = subprocess.run(command, cwd=tmp, env=env, capture_output=True, text=True,
                                    timeout=TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            return False, f"Stopped after {TIMEOUT_SECONDS} seconds (possible infinite loop)."
        output = (result.stdout + ("\n" + result.stderr if result.stderr.strip() else "")).strip()
        # Hide the temp folder path from tracebacks.
        output = output.replace(tmp + os.sep, "").replace(tmp, ".")
        return result.returncode == 0, output[-4000:]


def answer(question: str, file_name: str | None = None, file_data: bytes | None = None) -> Answer:
    prompt = question.strip()
    files = None
    if file_name and file_data is not None:
        files = {file_name: file_data}
        preview = file_data[:1500].decode("utf-8", errors="replace").splitlines()[:6]
        prompt += (f"\n\nThe file `{Path(file_name).name}` is in the current folder. Its first lines are:\n"
                   + "\n".join(preview)
                   + "\nIn the self-test, run the code on this file and print the result.")

    reply, seconds = llm.chat(llm.GENERAL_MODEL, prompt, system=SYSTEM, max_tokens=4096)
    code = _extract_code(reply)
    ok, output = run_sandboxed(code, files)
    passed = ok and PASS_MARKER in output
    attempts = 1

    if not passed:
        fix_prompt = (f"{prompt}\n\nYour previous code:\n```python\n{code}\n```\n\nRunning it gave:\n"
                      f"{output or '(no output)'}\n\nFix the code (and the self-test only if the test itself "
                      "was wrong). Reply with one ```python block.")
        reply, more = llm.chat(llm.GENERAL_MODEL, fix_prompt, system=SYSTEM, max_tokens=4096)
        seconds += more
        code = _extract_code(reply)
        ok, output = run_sandboxed(code, files)
        passed = ok and PASS_MARKER in output
        attempts = 2

    status = "✅ Ran and passed its tests" if passed else "⚠️ The code ran into a problem"
    if attempts == 2:
        status += " (after one fix)"
    # Output goes in its own block so the page shows it exactly (e.g. masked "****" isn't read as bold).
    text = f"```python\n{code}\n```\n\n{status}. Output:\n\n```text\n{output or '(no output)'}\n```"
    evidence = [f"Run in a sandbox: no network, temporary folder, {TIMEOUT_SECONDS}-second limit. "
                f"Attempts: {attempts}."]
    return Answer(text=text, kind=KIND, model=llm.GENERAL_MODEL, seconds=seconds, evidence=evidence)
