"""Test harness: run a practice pack through the same handlers the app uses, score it, and time it.

    .venv/bin/python -m desk.eval --pack data/practice/practice_pack
    .venv/bin/python -m desk.eval --pack data/practice/practice_pack --only audio --limit 5

Pack format (from the organizers' README): items.json (id, modality, file, question), answers.json
(reference_answer, answerable for text, transcript for speech, entry_point for code), media in
image/ audio/ text/ video/, and code/tests/<id>_test.py.

Scoring:
- code: the pack's own unit tests, run against our generated code in the sandbox (objective).
- text, unanswerable: correct only if we say the document doesn't contain it.
- counts: match a single unambiguous count; send answers with multiple numbers to human review.
- free-form answers: match a normalized whole phrase. Partial or ambiguous matches need human review.
- latency: wall time from loading an item to its final result (including retries and code unit tests).

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
    "sixteen seventeen eighteen nineteen twenty".split())} | {"hundred": 100, "thousand": 1000}
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
import ast, sys, types
sys.path.insert(0, ".")
solution = open("solution.py").read()
mod = types.ModuleType("solution")
exec(compile(solution, "solution.py", "exec"), mod.__dict__)
sys.modules["solution"] = mod
ns = {"__name__": "test"}
ns.update({k: v for k, v in mod.__dict__.items() if not k.startswith("__")})
suite = ast.parse(open("test_item.py").read(), filename="test_item.py")
exec(compile(suite, "test_item.py", "exec"), ns)
ran = sum(isinstance(statement, ast.Assert) for statement in suite.body)
entry = ENTRY_POINT
if "check" in ns and callable(ns["check"]) and entry and entry in ns:
    ns["check"](ns[entry]); ran += 1
for statement in suite.body:
    if isinstance(statement, ast.FunctionDef) and statement.name.startswith("test"):
        ns[statement.name](); ran += 1
print("UNIT TESTS PASSED" if ran else "NO TESTS FOUND")
'''


def run_unit_tests(solution: str, test_file: Path, entry_point: str | None) -> tuple[bool, str]:
    """Run the pack's unit tests against our code, in the same sandbox the app uses."""
    if not test_file.exists():
        return False, f"missing {test_file.name}"
    runner = _RUNNER.replace("ENTRY_POINT", repr(entry_point))
    files = {"solution.py": solution.encode(), "test_item.py": test_file.read_bytes()}
    ok, output = code.run_sandboxed(runner, files)
    return ok and output.splitlines()[-1:] == ["UNIT TESTS PASSED"], output


# ---------- scoring ----------

def _norm(s: str) -> str:
    s = s.lower().replace("’", "'").replace("'s ", " ").replace("s' ", "s ")
    s = re.sub(r"[^a-z0-9' ]+", " ", s)
    return " ".join(w for w in s.split() if w not in _STOP)


def _numbers(s: str) -> list[int]:
    return [int(token) if token.isdecimal() else _NUMBER_WORDS[token]
            for token in re.findall(r"\b(?:[0-9]+|[a-z]+)\b", s.lower())
            if token.isdecimal() or token in _NUMBER_WORDS]


def _final_answer(text: str) -> str:
    """If the model wrote reasoning first, score only its stated answer."""
    m = re.split(r"\*\*\s*answer\s*:?\s*\*\*\s*:?|\banswer\s*:", text, flags=re.I)
    return m[-1] if len(m) > 1 else text


def score(item: dict, answer: dict, ours: str, extra: dict) -> str:
    """Return 'correct', 'wrong' or 'review'."""
    modality = item["modality"]
    if modality == "code":
        return "correct" if extra.get("unit_tests_passed") else "wrong"
    if ours.startswith("ERROR:"):
        return "wrong"

    said_not_found = document.NOT_FOUND_MESSAGE.lower() in ours.lower()
    if modality == "text" and answer.get("answerable") is False:
        return "correct" if said_not_found else "wrong"
    if modality == "text" and said_not_found:
        return "wrong"

    question = item.get("question") or ""
    reference = str(answer.get("reference_answer") or "")
    final = _final_answer(ours)

    # Transcription questions: word error rate against the full transcript.
    transcript = answer.get("transcript")
    if transcript and re.search(r"transcri|what (is|was) (said|being said)|exact words", question, re.I):
        return "correct" if word_error_rate(transcript, ours) <= 0.25 else "review"

    # Page citations and evidence describe provenance, not the answer itself.
    final = re.sub(r"\(p(?:age)?\.?\s*\d+\)", "", final, flags=re.I)
    ref_head = re.split(r"[;(]|[.](?:\s|$)", reference, maxsplit=1)[0].strip()
    head_numbers = _numbers(ref_head)
    count_question = re.match(r"\s*how many\b", question, re.I)
    if head_numbers and (count_question or ref_head.isdecimal() or ref_head.lower() in _NUMBER_WORDS):
        ref_counts, ours_counts = set(head_numbers), set(_numbers(final))
        if not ours_counts or len(ref_counts) != 1 or len(ours_counts) != 1:
            return "review"
        if re.search(r"-\d|\d[./:]\d|\b(?:not|or|maybe)\b", final, re.I):
            return "review"
        return "correct" if ref_counts == ours_counts else "wrong"

    ref, got = _norm(reference), _norm(final)
    if ref and ref == got:
        return "correct"
    # A substring in a longer word, a negation, or a bag of shared words is not proof.
    if ref and f" {ref} " in f" {got} " and not re.search(r"\b(?:not|no|never|without)\b|n't\b", got):
        return "correct"
    # Nonmatching free-form descriptions may be synonyms; don't claim a machine verdict.
    return "review"



def word_error_rate(reference: str, hypothesis: str) -> float:
    # Preserve every word: dropped articles and pronouns are errors in a transcription.
    def words(text):
        return re.findall(r"[\w]+(?:'[\w]+)*", text.lower().replace("’", "'"))

    r = words(reference)
    h = words(re.sub(r"^\s*transcript:\s*", "", hypothesis, flags=re.I))
    if not r:
        return float(len(h))
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
        "| Input | Items | Automatically verified | Needs review | Wrong / error | Median s | Max s |",
        "|---|---|---|---|---|---|---|",
    ]
    for mod in ["image", "audio", "text", "video", "code"]:
        group = by_mod.get(mod)
        if not group:
            continue
        c = sum(r["score"] == "correct" for r in group)
        rv = sum(r["score"] == "review" for r in group)
        w = len(group) - c - rv
        secs = [r["seconds"] for r in group]
        lines.append(f"| {mod} | {len(group)} | {c} | {rv} | {w} | {statistics.median(secs):.1f} | {max(secs):.1f} |")
    total_c = sum(r["score"] == "correct" for r in rows)
    lines += ["", f"**Overall: {total_c}/{len(rows)} correct automatically**; "
                  f"{sum(r['score'] == 'review' for r in rows)} free-form answers need a person to check.",
              "", "How it's scored: see the docstring in `desk/eval.py`. Code uses the pack's own unit tests."]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n")


def rescore(pack: Path, items: list[dict], answers: dict, runs: list[Path], summary: Path):
    latest = {}
    for run in runs:
        for line in run.read_text().splitlines():
            d = json.loads(line)
            latest[d["id"]] = d
    rows = []
    by_id = {i["id"]: i for i in items}
    for item_id, d in latest.items():
        if item_id not in by_id:
            continue
        verdict = score(by_id[item_id], answers.get(item_id, {}), str(d["ours"]), d)
        rows.append({"id": item_id, "modality": d["modality"], "score": verdict, "seconds": d["seconds"]})
    write_summary(rows, pack, summary)
    print(summary.read_text())


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pack", default=str(ROOT / "data/practice/practice_pack"))
    ap.add_argument("--only", choices=["image", "audio", "text", "video", "code"])
    ap.add_argument("--limit", type=int, default=0, help="at most this many items per input type")
    ap.add_argument("--summary", default=str(ROOT / "results/test_results.md"))
    ap.add_argument("--rescore", nargs="+", metavar="RUN_JSONL",
                    help="rescore earlier runs from data/eval/ without calling the models (later files win per item)")
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

    if args.rescore:
        rescore(pack, items, answers, [Path(p) for p in args.rescore], Path(args.summary))
        return

    detail_dir = ROOT / "data/eval"
    detail_dir.mkdir(parents=True, exist_ok=True)
    detail_path = detail_dir / f"run_{datetime.now():%Y%m%d_%H%M%S}.jsonl"
    rows = []
    start = time.monotonic()
    with detail_path.open("w") as details:
        for n, item in enumerate(items, 1):
            ans = answers.get(item["id"], {})
            item_start = time.monotonic()
            try:
                ours, _, extra = run_item(pack, item, ans)
                verdict = score(item, ans, ours, extra)
            except Exception as e:  # keep going; an error counts as wrong
                ours, extra, verdict = f"ERROR: {e}", {}, "wrong"
            seconds = time.monotonic() - item_start
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
