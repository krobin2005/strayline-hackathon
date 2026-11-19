"""Focused OS-isolation smoke test. Run on the demo laptop with python -m unittest discover -s tests."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from desk.sandbox import SandboxUnavailable, run_sandboxed


class SandboxTests(unittest.TestCase):
    def test_missing_runtime_never_launches_code(self):
        with patch("desk.sandbox.RUNTIME", Path("/missing-strayline-runtime")), patch("desk.sandbox.subprocess.run") as run:
            with self.assertRaises(SandboxUnavailable):
                run_sandboxed("print('example')")
            run.assert_not_called()

    def test_input_and_os_isolation(self):
        # This marker is artificial and created specifically for this check.
        with tempfile.TemporaryDirectory() as outside:
            marker = Path(outside) / "marker.txt"
            marker.write_text("test-only")
            code = f"""
from pathlib import Path
assert Path('numbers.csv').read_text() == '17'
Path('report.txt').write_text('done')
marker = Path({str(marker)!r})
try:
    marker.read_text()
except (PermissionError, FileNotFoundError):
    pass
else:
    raise AssertionError('outside marker was readable')
try:
    marker.write_text('changed')
except (PermissionError, FileNotFoundError, OSError):
    pass
else:
    raise AssertionError('outside marker was writable')
try:
    import socket
    with socket.create_connection(('127.0.0.1', 11434), timeout=0.5):
        raise AssertionError('host model service is reachable')
except (OSError, ImportError, AttributeError):
    pass
print('sandbox smoke passed')
"""
            ok, output = run_sandboxed(code, {"numbers.csv": b"17"})
            self.assertTrue(ok, output)
            self.assertEqual(output, "sandbox smoke passed")
            self.assertEqual(marker.read_text(), "test-only")


if __name__ == "__main__":
    unittest.main()
