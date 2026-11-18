"""Logs: run the Strayline detector on an uploaded day of connection logs, then let the LLM brief the analyst.

The LLM only ever sees pseudonymized incident cards (no IPs, no labels).
"""

import json
import tempfile
from pathlib import Path

from .. import detector, llm
from ..router import LOGS
from . import Answer

# Results per uploaded file, so follow-up questions don't rerun the detector.
_cache: dict[str, detector.Report] = {}

SYSTEM = (
    "You are Strayline Desk, helping a college IT security analyst triage today's incidents. Each incident "
    "groups the alerts from one source host. Base rates: every incident is already unusual, and most are "
    "harmless, so unusual alone isn't evidence. Treat as serious a coherent pattern: very high rate or volume, "
    "spread across many hosts or ports, regular repetition, or the attack classifier agreeing across many "
    "connections. Be specific, cite incident numbers, and keep it short."
)
DEFAULT_QUESTION = ("Which incidents should I look at first, and why? Give the top 3 with a one-line reason "
                    "each, then say what kind of activity the top one most likely is.")


def _table(report: detector.Report, n: int = 10) -> str:
    lines = ["#  source        alerts  per min  targets  ports  started  fired by"]
    for i, c in enumerate(report.incidents[:n], 1):
        lines.append(f"{i:<2} {c['source']:<13} {c['alerts']:>6}  {c['alerts_per_min']:>7}  {c['distinct_targets']:>7}  "
                     f"{c['distinct_ports']:>5}  {c['start']:>7}  {c['fired_by']}")
    return "\n".join(lines)


def answer(cache_key: str, data: bytes, filename: str, question: str) -> Answer:
    det = detector.load_detector()
    if det is None:
        return Answer(text="The detector hasn't been trained on this laptop yet. Run:\n\n"
                           "```text\n.venv/bin/python -m desk.detector train\n```",
                      kind=LOGS, model="none", seconds=0.0)
    report = _cache.get(cache_key)
    detector_seconds = 0.0
    if report is None:
        with tempfile.NamedTemporaryFile(suffix=Path(filename).suffix or ".csv") as tmp:
            tmp.write(data)
            tmp.flush()
            report = detector.analyse(Path(tmp.name), det)
        _cache[cache_key] = report
        detector_seconds = report.seconds

    cards = [dict(n=i, **detector.public_card(c)) for i, c in enumerate(report.incidents[:8], 1)]
    prompt = (f"Today: {report.connections:,} connections, {report.alerts:,} alerts, "
              f"{report.incidents_total} incidents. Largest incidents:\n"
              + "\n".join(json.dumps(c) for c in cards)
              + f"\n\nQuestion: {question.strip() or DEFAULT_QUESTION}")
    briefing, seconds = llm.chat(llm.GENERAL_MODEL, prompt, system=SYSTEM)

    text = (f"{report.connections:,} connections → {report.alerts:,} alerts → {report.incidents_total} incidents "
            f"(detector: {report.seconds:.0f} s)\n\n```text\n{_table(report)}\n```\n\n{briefing}")
    evidence = ["Detector: classifier + anomaly score, 2% false-alarm budget set on normal traffic; "
                "alerts grouped per source host (10-minute gaps, at least 10 alerts). Hosts are pseudonymized."]
    if report.false_alarm_rate is not None:
        evidence.append(f"Scored against this file's lab labels (never shown to the models): "
                        f"{100 * report.false_alarm_rate:.2f}% of normal connections alerted, "
                        f"{100 * (report.attack_alert_rate or 0):.1f}% of attack connections alerted, "
                        f"{report.attack_incidents_in_top} attack incident(s) in the top {len(report.incidents)}.")
    return Answer(text=text, kind=LOGS, model=llm.GENERAL_MODEL, seconds=detector_seconds + seconds, evidence=evidence)
