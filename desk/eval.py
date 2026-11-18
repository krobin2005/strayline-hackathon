"""Test harness: run a practice pack through the same handlers the app uses, score it, and time it.

    .venv/bin/python -m desk.eval --pack data/practice/practice_pack
    .venv/bin/python -m desk.eval --pack data/practice/practice_pack --only audio --limit 5

Pack format (from the organizers' README): items.json (id, modality, file, question), answers.json
(reference_answer, answerable for text, transcript for speech, entry_point for code), media in
image/ audio/ text/ video/, and code/tests/<id>_test.py.

Scoring:
- code: the pack's own unit tests, run against our generated code in the sandbox (objective).
- text, unanswerable: correct only if we say the document doesn't contain it.
- numbers (counts): the first number in the reference must appear in our answer.
- everything else: normalized string match against the reference, then word overlap. Free-form
  answers that don't match automatically are marked "review" for a person to check, not counted wrong.

The answers are used only for scoring, after our answer is final; nothing is looked up.
Per-item details (which contain pack content) go to data/eval/ (git-ignored, per the pack's rules);
only aggregate numbers go to results/test_results.md.
"""

import argparse
import json
import platform
import re
import statistics
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from . import llm
from .handlers import audio, code, document, image, video

ROOT = Path(__file__).resolve().parent.parent
_NUMBER_WORDS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
    "sixteen seventeen eighteen nineteen twenty".split())}
_STOP = set("a an the of to in on at and or is are was were it this that there with for by as be".split())


# ---------- running ----------

def run_item(pack: Path, item: dict, answer: dict) -> tuple[str, float, dict]:
    """Return (our answer text, seconds, extra details)."""
    modality, question = item["modality"], item.get("question") or ""
    path = pack / item["file"] if item.get("file") else None
    data = path.read_bytes() if path else b""

    if modality == "image":
        r = image.answer(data, question)
    elif modality == "audio":
        r = audio.answer(data, path.name, question)
    elif modality == "video":
        r = video.answer(data, path.name, question)
    elif modality == "text":
        r = document.answer(data, path.name, question)
    elif modality == "code":
        result = code.write_and_test(question)
        test_file = pack / "code" / "tests" / f"{item['id']}_test.py"
        passed, output = run_unit_tests(result.code, test_file, answer.get("entry_point"))
        return result.code, result.seconds, {"unit_tests_passed": passed, "test_output": output[-1500:],
                                             "self_test_passed": result.passed, "attempts": result.attempts}
    else:
        raise ValueError(f"unknown modality {modality}")
    return r.text, r.seconds, {"evidence": r.evidence}


_RUNNER = '''
import sys, types
sys.path.insert(0, ".")
solution = open("solution.py").read()
mod = types.ModuleType("solution")
exec(compile(solution, "solution.py", "exec"), mod.__dict__)
sys.modules["solution"] = mod
ns = {"__name__": "test"}
ns.update({k: v for k, v in mod.__dict__.items() if not k.startswith("__")})
exec(compile(open("test_item.py").read(), "test_item.py", "exec"), ns)
ran = 0
entry = ENTRY_POINT
if "check" in ns and callable(ns["check"]) and entry and entry in ns:
    ns["check"](ns[entry]); ran += 1
for name, fn in list(ns.items()):
    if name.startswith("test") and callable(fn) and name != "test_item":
        fn(); ran += 1
print("UNIT TESTS PASSED" if ran or "assert" in open("test_item.py").read() else "NO TESTS FOUND")
'''


def run_unit_tests(solution: str, test_file: Path, entry_point: str | None) -> tuple[bool, str]:
    """Run the pack's unit tests against our code, in the same sandbox the app uses."""
    if not test_file.exists():
        return False, f"missing {test_file.name}"
    runner = _RUNNER.replace("ENTRY_POINT", repr(entry_point))
    files = {"solution.py": solution.encode(), "test_item.py": test_file.read_bytes()}
    ok, output = code.run_sandboxed(runner, files)
    return ok and "UNIT TESTS PASSED" in output, output


# ---------- scoring ----------

def _norm(s: str) -> str:
    s = s.lower().replace("’", "'")
    s = re.sub(r"[^a-z0-9' ]+", " ", s)
    return " ".join(w for w in s.split() if w not in _STOP)


def _numbers(s: str) -> list[int]:
    found = [int(n) for n in re.findall(r"\b\d+\b", s)]
    found += [_NUMBER_WORDS[w] for w in re.findall(r"[a-z]+", s.lower()) if w in _NUMBER_WORDS]
    return found


def score(item: dict, answer: dict, ours: str, extra: dict) -> str:
    """Return 'correct', 'wrong' or 'review'."""
    modality = item["modality"]
    if modality == "code":
        return "correct" if extra.get("unit_tests_passed") else "wrong"

    said_not_found = document.NOT_FOUND_MESSAGE.lower() in ours.lower()
    if modality == "text" and answer.get("answerable") is False:
        return "correct" if said_not_found else "wrong"
    if modality == "text" and said_not_found:
        return "wrong"

    reference = str(answer.get("reference_answer") or "")
    ref_head = re.split(r"[.(;]", reference, maxsplit=1)[0]  # e.g. "1 (1 person). A man..." -> "1 "
    head_numbers = _numbers(ref_head)
    if head_numbers and len(ref_head.split()) <= 3:
        return "correct" if head_numbers[0] in _numbers(ours) else "wrong"

    # Transcription questions: compare against the full transcript with word error rate.
    transcript = answer.get("transcript")
    if transcript and re.search(r"transcri|what (is|was) (said|being said)|exact words", item.get("question", ""), re.I):
        return "correct" if word_error_rate(transcript, ours) <= 0.25 else "review"

    ref, got = _norm(reference), _norm(ours)
    if ref and ref in got:
        return "correct"
    ref_words = set(ref.split())
    if ref_words and len(ref_words & set(got.split())) / len(ref_words) >= 0.6:
        return "correct" if len(ref_words) <= 4 else "review"
    return "review" if len(ref_words) > 4 else "wrong"


def word_error_rate(reference: str, hypothesis: str) -> float:
    r, h = _norm(reference).split(), _norm(hypothesis.replace("Transcript:", "")).split()
    if not r:
        return 0.0
    prev = list(range(len(h) + 1))
    for i, rw in enumerate(r, 1):
        cur = [i] + [0] * len(h)
        for j, hw in enumerate(h, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (rw != hw))
        prev = cur
    return prev[-1] / len(r)


# ---------- reporting ----------

def write_summary(rows: list[dict], pack: Path, out: Path):
    by_mod = defaultdict(list)
    for row in rows:
        by_mod[row["modality"]].append(row)
    lines = [
        "# Test results",
        "",
        f"Run {datetime.now():%Y-%m-%d %H:%M} on {platform.machine()} ({platform.platform(terse=True)}), "
        f"models `{llm.VISION_MODEL}` and `{llm.GENERAL_MODEL}` through Ollama, Wi-Fi not required.",
        f"Pack: `{pack.name}` ({len(rows)} items). Per-item answers stay local in `data/eval/` (pack rules).",
        "",
        "| Input | Items | Correct | Needs review | Wrong / error | Accuracy (auto-scored) | Median s | Max s |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for mod in ["image", "audio", "text", "video", "code"]:
        group = by_mod.get(mod)
        if not group:
            continue
        c = sum(r["score"] == "correct" for r in group)
        rv = sum(r["score"] == "review" for r in group)
        w = len(group) - c - rv
        scored = c + w
        secs = [r["seconds"] for r in group]
        acc = f"{100 * c / scored:.0f}%" if scored else "-"
        lines.append(f"| {mod} | {len(group)} | {c} | {rv} | {w} | {acc} | {statistics.median(secs):.1f} | {max(secs):.1f} |")
    total_c = sum(r["score"] == "correct" for r in rows)
    lines += ["", f"**Overall: {total_c}/{len(rows)} correct automatically**; "
                  f"{sum(r['score'] == 'review' for r in rows)} free-form answers need a person to check.",
              "", "How it's scored: see the docstring in `desk/eval.py`. Code uses the pack's own unit tests."]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pack", default=str(ROOT / "data/practice/practice_pack"))
    ap.add_argument("--only", choices=["image", "audio", "text", "video", "code"])
    ap.add_argument("--limit", type=int, default=0, help="at most this many items per input type")
    ap.add_argument("--summary", default=str(ROOT / "results/test_results.md"))
    args = ap.parse_args()

    pack = Path(args.pack)
    if not (pack / "items.json").exists():
        raise SystemExit(f"No items.json in {pack}. Download the practice pack from Kaggle and unzip it "
                         "into data/practice/ (see README).")
    items = json.loads((pack / "items.json").read_text())
    answers = {a["id"]: a for a in json.loads((pack / "answers.json").read_text())}
    if args.only:
        items = [i for i in items if i["modality"] == args.only]
    if args.limit:
        counts = defaultdict(int)
        items = [i for i in items if (counts.__setitem__(i["modality"], counts[i["modality"]] + 1)
                                      or counts[i["modality"]] <= args.limit)]
    # Group by input type so each model loads once.
    items.sort(key=lambda i: ["image", "video", "text", "audio", "code"].index(i["modality"])
               if i["modality"] in ("image", "video", "text", "audio", "code") else 9)

    detail_dir = ROOT / "data/eval"
    detail_dir.mkdir(parents=True, exist_ok=True)
    detail_path = detail_dir / f"run_{datetime.now():%Y%m%d_%H%M%S}.jsonl"
    rows = []
    start = time.monotonic()
    with detail_path.open("w") as details:
        for n, item in enumerate(items, 1):
            ans = answers.get(item["id"], {})
            try:
                ours, seconds, extra = run_item(pack, item, ans)
                verdict = score(item, ans, ours, extra)
            except Exception as e:  # keep going; an error counts as wrong
                ours, seconds, extra, verdict = f"ERROR: {e}", 0.0, {}, "wrong"
            rows.append({"id": item["id"], "modality": item["modality"], "score": verdict, "seconds": seconds})
            details.write(json.dumps({**rows[-1], "question": item.get("question"), "ours": ours,
                                      "reference": ans.get("reference_answer"), **extra}) + "\n")
            details.flush()
            print(f"[{n}/{len(items)}] {item['id']:<14} {verdict:<8} {seconds:5.1f}s  "
                  f"{' '.join(str(ours).split())[:90]}", flush=True)

    write_summary(rows, pack, Path(args.summary))
    print(f"\nDone in {time.monotonic() - start:.0f}s. Summary: {args.summary}  Details: {detail_path}")


if __name__ == "__main__":
    main()
