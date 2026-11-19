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
    "Brief a campus IT analyst using only the supplied connection summaries. Incident numbers are "
    "ranks by alert volume, not diagnoses. Compare incidents by their share of the file's alerts, "
    "alerts per minute, target and port counts, and number of classifier flags. A high sustained "
    "rate aimed at one service can support a possible flood. Hundreds of distinct targets or ports "
    "from one source within minutes can support a possible scan or sweep. Hundreds of MB sent to one "
    "outside host can support possible data exfiltration. A few anomaly flags across ordinary "
    "services do not establish a scan, compromise, or malicious intent. Do not promote a quota of "
    "incidents or invent traffic details. Identify uncertainty and one concrete verification step. "
    "Answer the analyst's question directly and concisely."
)
DEFAULT_QUESTION = "Which incident, if any, warrants investigation first? Cite the measurements and explain why."


def _table(report: detector.Report, n: int = 10) -> str:
    lines = ["#  source        alerts  per min  targets  ports  started  fired by"]
    for i, c in enumerate(report.incidents[:n], 1):
        lines.append(f"{i:<2} {c['source']:<13} {c['alerts']:>6}  {c['alerts_per_min']:>7}  {c['distinct_targets']:>7}  "
                     f"{c['distinct_ports']:>5}  {c['start']:>7}  {c['fired_by']}")
    return "\n".join(lines)


def answer(cache_key: str, data: bytes, filename: str, question: str) -> Answer:
    report = _cache.get(cache_key)
    detector_seconds = 0.0
    if report is None:
        det = detector.load_detector()
        if det is None:
            return Answer(
                text="The detector hasn't been trained on this laptop yet. Run:\n\n"
                     "```text\n.venv/bin/python -m desk.detector train\n```",
                kind=LOGS, model="none", seconds=0.0,
            )
        with tempfile.NamedTemporaryFile(suffix=Path(filename).suffix or ".csv") as tmp:
            tmp.write(data)
            tmp.flush()
            report = detector.analyse(Path(tmp.name), det)
        _cache[cache_key] = report
        detector_seconds = report.seconds

    if not report.incidents:
        return Answer(text=f"{report.connections:,} connections, {report.alerts:,} alerts. No source host "
                           f"formed an incident of at least {detector.MIN_ALERTS} alerts within the grouping window.",
                      kind=LOGS, model="detector", seconds=detector_seconds)

    cards = [dict(n=i, share_of_all_alerts_pct=round(100 * c["alerts"] / report.alerts, 2),
                  **detector.public_card(c)) for i, c in enumerate(report.incidents, 1)]
    prompt = (f"File totals: {report.connections:,} connections, {report.alerts:,} detector alerts, "
              f"{report.incidents_total} grouped incidents. Top {len(cards)} by alert count:\n"
              + "\n".join(json.dumps(c) for c in cards)
              + f"\n\nQuestion: {question.strip() or DEFAULT_QUESTION}")
    briefing, seconds = llm.chat(llm.GENERAL_MODEL, prompt, system=SYSTEM)

    text = (f"{report.connections:,} connections → {report.alerts:,} alerts → {report.incidents_total} incidents "
            f"(detector: {report.seconds:.0f} s)\n\n```text\n{_table(report)}\n```\n\n{briefing}")
    evidence = ["Detector: classifier + anomaly score, 2% false-alarm budget set on normal traffic; "
                "alerts grouped per source host (10-minute gaps, at least 10 alerts). Hosts are pseudonymized."]
    metrics = []
    if report.false_alarm_rate is not None:
        metrics.append(f"{100 * report.false_alarm_rate:.2f}% of known normal connections alerted")
    if report.attack_alert_rate is not None:
        metrics.append(f"{100 * report.attack_alert_rate:.1f}% of known attack connections alerted")
    if metrics:
        evidence.append("Evaluated against lab labels after scoring: " + "; ".join(metrics) + ".")
    return Answer(text=text, kind=LOGS, model=llm.GENERAL_MODEL, seconds=detector_seconds + seconds, evidence=evidence)
