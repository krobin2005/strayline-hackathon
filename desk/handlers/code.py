"""Code: write Python from a prompt, then prove it works by running it in a sandbox.

Flow: Gemma 4 E4B writes the code plus a small self-test → we run it in a separate process
(no network, temporary folder, 10-second limit) → if it fails, the error goes back to the model
(up to twice) for a fix → the user sees the code, the output and whether its tests passed.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from .. import llm
from ..sandbox import TIMEOUT_SECONDS, run_sandboxed
from . import Answer

KIND = "code"
PASS_MARKER = "ALL TESTS PASSED"
MAX_ATTEMPTS = 3  # the first try plus two fixes

_CODE_REQUEST = re.compile(
    r"\b(write|create|generate|implement|code|build|make)\b.{0,60}\b(function|script|program|code|class|"
    r"regex|regular expression|parser|query|snippet|method)\b|\bin python\b|\bpython (function|script|code)\b",
    re.IGNORECASE | re.DOTALL,
)
# A pasted function stub ("def f(x):" plus a docstring), the format of the challenge's code items.
_CODE_STUB = re.compile(r"^\s*(def |from \w+ import |import \w+)", re.MULTILINE)

SYSTEM = (
    "You write correct, simple Python 3 code. Reply with exactly one ```python code block and nothing "
    "else. Use only the standard library unless the user names a library. The block must contain:\n"
    "1. the code the user asked for;\n"
    "2. at the end, under `if __name__ == \"__main__\":`, a short self-test that calls it on 2-4 "
    "realistic examples, checks the results with `assert`, prints each result, and finally prints "
    f"exactly `{PASS_MARKER}`.\n"
    "Think about edge cases before writing. Do not read or write files unless asked; never use the network."
)

def is_code_request(question: str) -> bool:
    question = question or ""
    return bool(_CODE_REQUEST.search(question) or _CODE_STUB.search(question))


def _extract_code(reply: str) -> str:
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", reply, re.DOTALL)
    return max(blocks, key=len).strip() if blocks else reply.strip()


@dataclass
class CodeResult:
    code: str
    passed: bool  # ran without error and its own self-test passed
    output: str
    attempts: int
    seconds: float


def write_and_test(question: str, file_name: str | None = None, file_data: bytes | None = None) -> CodeResult:
    """Write code for the request, run it in the sandbox, and fix it up to twice if it fails."""
    prompt = question.strip()
    if _CODE_STUB.search(prompt):
        prompt = ("Complete this Python code. Keep every function name and signature exactly as given, "
                  "and follow the docstring and its examples precisely.\n\n" + prompt)
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

    # Up to two fix rounds: each gets the latest code and its error.
    while not passed and attempts < MAX_ATTEMPTS:
        fix_prompt = (f"{prompt}\n\nYour previous code:\n```python\n{code}\n```\n\nRunning it gave:\n"
                      f"{output or '(no output)'}\n\nFix the code (and the self-test only if the test itself "
                      "was wrong). Reply with one ```python block.")
        reply, more = llm.chat(llm.GENERAL_MODEL, fix_prompt, system=SYSTEM, max_tokens=4096)
        seconds += more
        code = _extract_code(reply)
        ok, output = run_sandboxed(code, files)
        passed = ok and PASS_MARKER in output
        attempts += 1
    return CodeResult(code=code, passed=passed, output=output, attempts=attempts, seconds=seconds)


def answer(question: str, file_name: str | None = None, file_data: bytes | None = None) -> Answer:
    r = write_and_test(question, file_name, file_data)
    status = "✅ Ran and passed its tests" if r.passed else "⚠️ The code ran into a problem"
    if r.attempts > 1:
        fixes = r.attempts - 1
        status += f" (after {fixes} fix{'es' if fixes > 1 else ''})"
    # Output goes in its own block so the page shows it exactly (e.g. masked "****" isn't read as bold).
    text = f"```python\n{r.code}\n```\n\n{status}. Output:\n\n```text\n{r.output or '(no output)'}\n```"
    evidence = [f"Run in a sandbox: no network, temporary folder, {TIMEOUT_SECONDS}-second limit. "
                f"Attempts: {r.attempts}."]
    return Answer(text=text, kind=KIND, model=llm.GENERAL_MODEL, seconds=r.seconds, evidence=evidence)
