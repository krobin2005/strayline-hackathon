"""Strayline detector (lite): a day of connection logs -> ranked incidents. Spec: README §4 "Logs".

    .venv/bin/python -m desk.detector train                 # fit on CIC-IDS2017 Mon/Tue/Thu/Fri (~2 min)
    .venv/bin/python -m desk.detector score data/raw/wednesday.csv

Two detectors per connection, alert if either fires, thresholds set jointly on benign validation
traffic so 2% of normal connections alert in total:
- a classifier (MLP) trained on labelled attacks from Tue/Thu/Fri; it never sees Wednesday's DoS;
- a kNN anomaly score: distance to normal traffic (Monday), which catches what the classifier hasn't seen.
Alerts are grouped per source host into incidents (new incident after 10 quiet minutes, >= 10 alerts).
Labels in the file are used only to report detection rates, never as model input or shown to the LLM.
"""

import ipaddress
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.neural_network import MLPClassifier

ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = ROOT / "data/models/detector.joblib"
BUDGET = 0.02            # share of normal connections allowed to alert
KNN_REFERENCE = 10_000   # normal connections kept for the kNN score
KNN_K = 5
GAP_SECONDS = 600        # a new incident starts after 10 quiet minutes
MIN_ALERTS = 10

FLOW_FEATURES = [
    "duration_us", "proto", "fwd_pkts", "bwd_pkts", "fwd_bytes", "bwd_bytes", "bytes_per_s", "pkts_per_s",
    "fwd_pkts_per_s", "bwd_pkts_per_s", "fwd_pkt_len_mean", "bwd_pkt_len_mean", "avg_pkt_size",
    "down_up_ratio", "fin", "syn", "rst", "psh", "ack",
]
HOST_FEATURES = ["src_flows_1m", "src_dst_hosts_1m", "src_dst_ports_1m", "src_short_frac_1m",
                 "dst_flows_1m", "dst_src_hosts_1m", "dst_short_frac_1m"]
ALL_FEATURES = FLOW_FEATURES + HOST_FEATURES

FAMILIES = {  # raw CIC-IDS2017 label prefix -> family
    "DoS": "DoS", "DDoS": "DDoS", "PortScan": "PortScan", "Portscan": "PortScan", "FTP-Patator": "BruteForce",
    "SSH-Patator": "BruteForce", "Botnet": "Botnet", "Bot": "Botnet", "Web Attack": "WebAttack",
    "Infiltration": "Infiltration",
}
_CSV_COLUMNS = {
    "Src IP": "src", "Dst IP": "dst", "Dst Port": "dst_port", "Protocol": "proto", "Timestamp": "timestamp",
    "Flow Duration": "duration_us", "Total Fwd Packet": "fwd_pkts", "Total Bwd packets": "bwd_pkts",
    "Total Length of Fwd Packet": "fwd_bytes", "Total Length of Bwd Packet": "bwd_bytes",
    "FIN Flag Count": "fin", "SYN Flag Count": "syn", "RST Flag Count": "rst", "PSH Flag Count": "psh",
    "ACK Flag Count": "ack", "Label": "label",
}


# ---------- loading and features ----------

def load(path: Path) -> pd.DataFrame:
    """Read a CIC-IDS2017-style CSV (only the columns a flow record has) and compute all features."""
    header = pd.read_csv(path, nrows=0).columns
    usecols = [c for c in _CSV_COLUMNS if c in header]
    df = pd.read_csv(path, usecols=usecols, low_memory=False).rename(columns=_CSV_COLUMNS)
    # Seconds since epoch, computed with timedelta arithmetic (dividing raw nanoseconds once made a day 1.7 h long).
    ts = pd.to_datetime(df["timestamp"], errors="coerce")
    df["ts"] = (ts - pd.Timestamp("1970-01-01")) / pd.Timedelta(seconds=1)
    df = df.dropna(subset=["ts"]).reset_index(drop=True)
    if "label" in df:
        # Unknown or excluded lab labels are unscored. Keep their traffic for inference.
        families = {label: _family(label) for label in df["label"].dropna().unique()}
        df["family"] = df["label"].map(families)
    span_h = (df["ts"].max() - df["ts"].min()) / 3600
    assert span_h < 30, f"{path.name}: timestamps span {span_h:.1f} h; expected about one day"
    return add_features(df)


def _family(label: str) -> str | None:
    label = str(label)
    if "attempted" in label.lower() or "heartbleed" in label.lower():
        return None
    if label.upper() == "BENIGN":
        return "Benign"
    if "portscan" in label.lower():  # incl. "Infiltration - Portscan", a scan from a compromised host
        return "PortScan"
    for prefix, family in FAMILIES.items():
        if label.startswith(prefix):
            return family
    return None


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    seconds = df["duration_us"].clip(lower=0) / 1e6
    has_time = seconds > 0
    safe = seconds.where(has_time, 1.0)
    fp, bp, fb, bb = (df[c].astype(float) for c in ("fwd_pkts", "bwd_pkts", "fwd_bytes", "bwd_bytes"))
    df["bytes_per_s"] = np.where(has_time, (fb + bb) / safe, 0.0)
    df["pkts_per_s"] = np.where(has_time, (fp + bp) / safe, 0.0)
    df["fwd_pkts_per_s"] = np.where(has_time, fp / safe, 0.0)
    df["bwd_pkts_per_s"] = np.where(has_time, bp / safe, 0.0)
    df["fwd_pkt_len_mean"] = np.where(fp > 0, fb / fp.where(fp > 0, 1), 0.0)
    df["bwd_pkt_len_mean"] = np.where(bp > 0, bb / bp.where(bp > 0, 1), 0.0)
    total = fp + bp
    df["avg_pkt_size"] = np.where(total > 0, (fb + bb) / total.where(total > 0, 1), 0.0)
    df["down_up_ratio"] = np.where(fp > 0, bp / fp.where(fp > 0, 1), 0.0)
    for flag in ("fin", "syn", "rst", "psh", "ack"):
        df[flag] = (df[flag] > 0).astype(float)  # flow records only know whether a flag appeared

    # Per-host features per clock minute, on the full file (never after sampling).
    minute = (df["ts"] // 60).astype(np.int64)
    short = (fp <= 2).astype(float)
    src = df.groupby([df["src"], minute])
    df["src_flows_1m"] = src["dst"].transform("size")
    df["src_dst_hosts_1m"] = src["dst"].transform("nunique")
    df["src_dst_ports_1m"] = src["dst_port"].transform("nunique")
    df["src_short_frac_1m"] = short.groupby([df["src"], minute]).transform("mean")
    dst = df.groupby([df["dst"], minute])
    df["dst_flows_1m"] = dst["src"].transform("size")
    df["dst_src_hosts_1m"] = dst["src"].transform("nunique")
    df["dst_short_frac_1m"] = short.groupby([df["dst"], minute]).transform("mean")
    return df


# ---------- scaling ----------

@dataclass
class Scaler:
    mean: np.ndarray
    std: np.ndarray

    @classmethod
    def fit(cls, x: np.ndarray) -> "Scaler":
        z = np.sign(x) * np.log1p(np.abs(x))
        return cls(z.mean(0), np.maximum(z.std(0), 0.1))  # floor stops constant features exploding

    def __call__(self, x: np.ndarray) -> np.ndarray:
        z = np.sign(x) * np.log1p(np.abs(x))
        return np.clip((z - self.mean) / self.std, -10, 10).astype(np.float32)


# ---------- model ----------

@dataclass
class Detector:
    scaler_all: Scaler
    scaler_flow: Scaler
    classifier: MLPClassifier
    reference: np.ndarray            # scaled flow features of normal traffic, for kNN
    thresholds: dict = field(default_factory=dict)

    def scores(self, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        clf = self.classifier.predict_proba(self.scaler_all(df[ALL_FEATURES].to_numpy(float)))[:, 1]
        return clf, knn_distance(self.scaler_flow(df[FLOW_FEATURES].to_numpy(float)), self.reference)


def knn_distance(x: np.ndarray, reference: np.ndarray, k: int = KNN_K, batch: int = 4096) -> np.ndarray:
    ref_sq = (reference ** 2).sum(1)
    out = np.empty(len(x), np.float32)
    for i in range(0, len(x), batch):
        b = x[i:i + batch]
        d2 = (b ** 2).sum(1)[:, None] + ref_sq[None, :] - 2 * b @ reference.T
        nearest = np.partition(np.maximum(d2, 0), k, axis=1)[:, :k]
        out[i:i + batch] = np.sqrt(nearest).mean(1)
    return out


def joint_thresholds(clf: np.ndarray, knn: np.ndarray, budget: float = BUDGET) -> dict:
    """Thresholds for the two arms so that alerting if EITHER fires flags `budget` of normal traffic."""
    lo, hi = 0.0, budget
    for _ in range(40):
        q = (lo + hi) / 2
        t_clf, t_knn = np.quantile(clf, 1 - q), np.quantile(knn, 1 - q)
        union = np.mean((clf > t_clf) | (knn > t_knn))
        lo, hi = (q, hi) if union < budget else (lo, q)
    q = lo
    return {"classifier": float(np.quantile(clf, 1 - q)), "knn": float(np.quantile(knn, 1 - q))}


def _chronological(df: pd.DataFrame, start: float, end: float) -> pd.DataFrame:
    """The slice of each (family) group between two fractions of its time order."""
    parts = []
    for _, g in df.sort_values("ts").groupby("family"):
        n = len(g)
        parts.append(g.iloc[int(n * start):int(n * end)])
    return pd.concat(parts)


def train(raw_dir: Path = ROOT / "data/raw", seed: int = 0) -> Detector:
    rng = np.random.default_rng(seed)
    t0 = time.monotonic()
    days = {d: load(raw_dir / f"{d}.csv") for d in ("monday", "tuesday", "thursday", "friday")}
    print(f"loaded training days in {time.monotonic() - t0:.0f}s")
    train_parts = [_chronological(df, 0.0, 0.6) for df in days.values()]
    val_parts = [_chronological(df, 0.6, 0.8) for df in days.values()]
    tr, va = pd.concat(train_parts), pd.concat(val_parts)
    benign_tr = tr[tr["family"] == "Benign"]
    benign_va = va[va["family"] == "Benign"]

    scaler_all = Scaler.fit(benign_tr[ALL_FEATURES].to_numpy(float))
    scaler_flow = Scaler.fit(benign_tr[FLOW_FEATURES].to_numpy(float))

    # Classifier: up to 150k benign + up to 30k per attack family, so floods don't dominate.
    pieces = [benign_tr.sample(min(150_000, len(benign_tr)), random_state=seed)]
    for fam, g in tr[tr["family"] != "Benign"].groupby("family"):
        pieces.append(g.sample(min(30_000, len(g)), random_state=seed))
    fit = pd.concat(pieces)
    y = (fit["family"] != "Benign").astype(int).to_numpy()
    print("classifier training set:", fit["family"].value_counts().to_dict())
    clf = MLPClassifier(hidden_layer_sizes=(128, 64), batch_size=2048, learning_rate_init=1e-3,
                        max_iter=8, random_state=seed)
    clf.fit(scaler_all(fit[ALL_FEATURES].to_numpy(float)), y)

    # kNN reference: normal Monday traffic only (the "site's own normal").
    monday_benign = days["monday"]
    monday_benign = _chronological(monday_benign[monday_benign["family"] == "Benign"], 0.0, 0.6)
    idx = rng.choice(len(monday_benign), min(KNN_REFERENCE, len(monday_benign)), replace=False)
    reference = scaler_flow(monday_benign[FLOW_FEATURES].to_numpy(float)[idx])

    det = Detector(scaler_all, scaler_flow, clf, reference)
    val_sample = benign_va.sample(min(100_000, len(benign_va)), random_state=seed)
    det.thresholds = joint_thresholds(*det.scores(val_sample))
    print(f"thresholds {det.thresholds}  (trained in {time.monotonic() - t0:.0f}s)")
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(det, MODEL_PATH)
    print(f"saved {MODEL_PATH}")
    return det


def load_detector() -> Detector | None:
    return joblib.load(MODEL_PATH) if MODEL_PATH.exists() else None


# ---------- incidents ----------

_LAN = [ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7")]


class Pseudonyms:
    """int-host-N / ext-host-N names, so neither the LLM nor the screen shows real addresses."""

    def __init__(self):
        self.names: dict[str, str] = {}

    def __call__(self, ip: str) -> str:
        if ip not in self.names:
            try:
                address = ipaddress.ip_address(ip)
                # LAN ranges only: Python's is_private also covers documentation ranges such as 203.0.113.0/24.
                internal = any(address in net for net in _LAN if net.version == address.version)
            except ValueError:
                internal = False
            prefix = "int-host" if internal else "ext-host"
            self.names[ip] = f"{prefix}-{sum(n.startswith(prefix) for n in self.names.values()) + 1}"
        return self.names[ip]


@dataclass
class Report:
    connections: int
    alerts: int
    incidents: list[dict]
    seconds: float
    false_alarm_rate: float | None = None      # only if the file has labels
    attack_alert_rate: float | None = None
    attack_incidents_in_top: int | None = None
    incidents_total: int = 0


def analyse(path: Path, det: Detector, top: int = 20) -> Report:
    t0 = time.monotonic()
    df = load(path)
    clf, knn = det.scores(df)
    fired_clf, fired_knn = clf > det.thresholds["classifier"], knn > det.thresholds["knn"]
    df["alert"], df["by_clf"], df["by_knn"] = fired_clf | fired_knn, fired_clf, fired_knn
    alerts = df[df["alert"]].sort_values(["src", "ts"])

    names = Pseudonyms()
    incidents = []
    for src_ip, g in alerts.groupby("src"):
        new = g["ts"].diff().fillna(0) > GAP_SECONDS
        for _, inc in g.groupby(new.cumsum()):
            if len(inc) < MIN_ALERTS:
                continue
            minutes = max((inc["ts"].max() - inc["ts"].min()) / 60, 1 / 60)
            z = det.scaler_all(inc[ALL_FEATURES].to_numpy(float))
            unusual = np.argsort(-np.abs(np.median(z, 0)))[:3]
            card = {
                "source": names(src_ip),
                "example_targets": sorted({names(d) for d in inc["dst"].unique()[:5]}),  # up to 5; see distinct_targets
                "start": pd.to_datetime(inc["ts"].min(), unit="s").strftime("%H:%M"),
                "minutes": round(minutes, 1),
                "alerts": int(len(inc)),
                "alerts_per_min": round(len(inc) / minutes, 1),
                "distinct_targets": int(inc["dst"].nunique()),
                "distinct_ports": int(inc["dst_port"].nunique()),
                "mb_sent": round(float(inc["fwd_bytes"].sum()) / 1e6, 1),
                "mb_received": round(float(inc["bwd_bytes"].sum()) / 1e6, 1),
                "top_ports": [int(p) for p in inc["dst_port"].value_counts().index[:5]],
                "classifier_flags": int(inc["by_clf"].sum()),
                "anomaly_flags": int(inc["by_knn"].sum()),
                "fired_by": f"classifier {100 * inc['by_clf'].mean():.0f}%, anomaly {100 * inc['by_knn'].mean():.0f}%",
                "unusual": ", ".join(f"{ALL_FEATURES[i]} {np.median(inc[ALL_FEATURES[i]]):.3g}" for i in unusual),
            }
            if "family" in inc:  # ground truth for scoring only; stripped before any LLM sees the card
                mode = inc["family"].mode()
                card["_truth"] = mode.iat[0] if not mode.empty else None
            incidents.append(card)
    incidents.sort(key=lambda c: -c["alerts"])

    report = Report(connections=len(df), alerts=int(df["alert"].sum()), incidents=incidents[:top],
                    incidents_total=len(incidents), seconds=time.monotonic() - t0)
    if "family" in df:
        benign = df["family"] == "Benign"
        attack = df["family"].notna() & ~benign
        report.false_alarm_rate = float(df.loc[benign, "alert"].mean()) if benign.any() else None
        report.attack_alert_rate = float(df.loc[attack, "alert"].mean()) if attack.any() else None
        report.attack_incidents_in_top = sum(c.get("_truth") not in (None, "Benign") for c in incidents[:top])
    return report


def public_card(card: dict) -> dict:
    return {k: v for k, v in card.items() if not k.startswith("_")}


def main():
    # Use the imported module, not __main__, so saved models load inside the app too (pickle stores class paths).
    import desk.detector as module
    if len(sys.argv) >= 2 and sys.argv[1] == "train":
        module.train()
    elif len(sys.argv) >= 3 and sys.argv[1] == "score":
        det = module.load_detector() or sys.exit("Train first: python -m desk.detector train")
        r = module.analyse(Path(sys.argv[2]), det)
        print(f"{r.connections:,} connections -> {r.alerts:,} alerts -> {r.incidents_total} incidents "
              f"({r.seconds:.0f}s)")
        if r.false_alarm_rate is not None:
            print(f"false alarms on known normal traffic: {100 * r.false_alarm_rate:.2f}%")
        if r.attack_alert_rate is not None:
            print(f"known attack connections alerted: {100 * r.attack_alert_rate:.1f}%")
        if r.attack_incidents_in_top is not None:
            print(f"majority-attack incidents in top {len(r.incidents)}: {r.attack_incidents_in_top}")
        for c in r.incidents[:10]:
            print(json.dumps(c))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
