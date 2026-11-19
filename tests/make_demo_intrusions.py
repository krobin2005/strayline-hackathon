"""Build the logs demo: two quiet hours of real lab traffic with five planted, synthetic intrusions.

    .venv/bin/python tests/make_demo_intrusions.py       # writes data/demo/campus_afternoon.csv (~5 MB)
    .venv/bin/python -m desk.detector score data/demo/campus_afternoon.csv

Background: every flow from CIC-IDS2017 Wednesday 15:00-17:00, a window with no labelled attacks,
on a day the detector never trained on. On top of it we plant five intrusions on fictional hosts
(TEST-NET addresses for outsiders), written as flow records with the same columns:

  1. SMB sweep    an infected laptop touches port 445 on every internal address  (lateral movement)
  2. port scan    the same laptop then probes 1,000 ports on the file server        (reconnaissance)
  3. SSH guessing an outside host tries passwords on the server for 25 minutes     (brute force)
  4. HTTP flood   an outside host floods the web server for 3 minutes             (denial of service)
  5. exfiltration the infected laptop uploads ~1.5 GB to an outside host, later  (data theft)

The detector is not tuned on this file. The planted rows carry a Label so the CLI can report how
many it alerted on; the app never shows labels to the language model. This is a demo, not a
benchmark: the intrusions are our own synthetic flows, and the background is lab traffic.
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data/raw/wednesday.csv"
OUT = ROOT / "data/demo/campus_afternoon.csv"
COLUMNS = ["Src IP", "Src Port", "Dst IP", "Dst Port", "Protocol", "Timestamp", "Flow Duration",
           "Total Fwd Packet", "Total Bwd packets", "Total Length of Fwd Packet", "Total Length of Bwd Packet",
           "FIN Flag Count", "SYN Flag Count", "RST Flag Count", "PSH Flag Count", "ACK Flag Count", "Label"]
START, END = pd.Timestamp("2017-07-05 15:00"), pd.Timestamp("2017-07-05 17:00")

LAPTOP = "192.168.10.77"      # the infected campus laptop (not a host in the lab data)
FILE_SERVER = "192.168.10.50"
GUESSER, FLOODER, DROP = "203.0.113.45", "203.0.113.99", "198.51.100.23"

rng = np.random.default_rng(7)


def flows(n, t0, seconds, src, dst, dport, *, dur_us, fwd_pkts, bwd_pkts, fwd_bytes, bwd_bytes,
          flags, label, proto=6):
    """n flow records spread over `seconds` from t0. Size arguments are (low, high) ranges."""
    def draw(r):
        return rng.integers(r[0], r[1] + 1, n)
    times = t0 + pd.to_timedelta(np.sort(rng.uniform(0, seconds, n)), unit="s")
    rows = pd.DataFrame({
        "Src IP": src, "Src Port": rng.integers(40000, 65000, n), "Dst IP": dst,
        "Dst Port": dport if np.ndim(dport) else np.full(n, dport), "Protocol": proto,
        "Timestamp": times.strftime("%Y-%m-%d %H:%M:%S.%f"), "Flow Duration": draw(dur_us),
        "Total Fwd Packet": draw(fwd_pkts), "Total Bwd packets": draw(bwd_pkts),
        "Total Length of Fwd Packet": draw(fwd_bytes), "Total Length of Bwd Packet": draw(bwd_bytes),
        "Label": label,
    })
    for flag in ("FIN", "SYN", "RST", "PSH", "ACK"):
        rows[f"{flag} Flag Count"] = int(flag in flags)
    return rows


def planted() -> pd.DataFrame:
    t = lambda hhmm: pd.Timestamp(f"2017-07-05 {hhmm}")
    internal = [f"192.168.10.{i}" for i in range(1, 255) if i != 77]
    return pd.concat([
        flows(len(internal), t("15:20"), 70, LAPTOP, internal, 445, dur_us=(40, 900), fwd_pkts=(1, 2),
              bwd_pkts=(0, 1), fwd_bytes=(0, 0), bwd_bytes=(0, 0), flags="SYN RST", label="PortScan - SMB sweep"),
        flows(1000, t("15:23"), 90, LAPTOP, FILE_SERVER, rng.permutation(np.arange(1, 1025))[:1000],
              dur_us=(30, 400), fwd_pkts=(1, 1), bwd_pkts=(1, 1), fwd_bytes=(0, 0), bwd_bytes=(0, 0),
              flags="SYN RST", label="PortScan"),
        flows(420, t("15:40"), 25 * 60, GUESSER, FILE_SERVER, 22, dur_us=(2_000_000, 6_000_000),
              fwd_pkts=(12, 22), bwd_pkts=(16, 30), fwd_bytes=(1200, 2600), bwd_bytes=(2400, 4200),
              flags="SYN FIN PSH ACK", label="SSH-Patator"),
        flows(3000, t("16:10"), 180, FLOODER, FILE_SERVER, 80, dur_us=(1_000, 120_000), fwd_pkts=(3, 5),
              bwd_pkts=(2, 4), fwd_bytes=(250, 450), bwd_bytes=(0, 400), flags="SYN PSH ACK", label="DoS Flood"),
        flows(40, t("16:00"), 55 * 60, LAPTOP, DROP, 443, dur_us=(60_000_000, 90_000_000),
              fwd_pkts=(15_000, 45_000), bwd_pkts=(5_000, 15_000), fwd_bytes=(20_000_000, 60_000_000),
              bwd_bytes=(200_000, 800_000), flags="PSH ACK", label="Exfiltration"),
    ])


def main():
    df = pd.read_csv(SOURCE, usecols=COLUMNS, low_memory=False)
    ts = pd.to_datetime(df["Timestamp"])
    background = df[(ts >= START) & (ts < END)]
    assert (background["Label"] == "BENIGN").mean() > 0.999, "the background window should be attack-free"
    out = pd.concat([background, planted()], ignore_index=True)
    out = out.sort_values("Timestamp", kind="stable")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(background):,} background + {len(out) - len(background):,} planted flows")


if __name__ == "__main__":
    main()
