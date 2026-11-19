"""Install the checksum-pinned WASI Python distribution during the online setup step."""
import hashlib
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from .sandbox import RUNTIME

URL = "https://github.com/brettcannon/cpython-wasi-build/releases/download/v3.14.4/python-3.14.4-wasi_sdk-24.zip"
SHA256 = "c2692ac10a380d4545d990b05bb30ae590c98b4642340452179800d18a6849ab"


def install():
    if (RUNTIME / "python.wasm").is_file():
        return
    RUNTIME.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=RUNTIME.parent) as tmp:
        archive = Path(tmp) / "runtime.zip"
        urllib.request.urlretrieve(URL, archive)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
            raise ValueError("Python sandbox download did not match its published SHA-256.")
        staged = Path(tmp) / "unpacked"
        with zipfile.ZipFile(archive) as source:
            source.extractall(staged)
        staged.rename(RUNTIME)


if __name__ == "__main__":
    install()
