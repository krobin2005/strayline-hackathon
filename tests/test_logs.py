"""Regression checks on the detector and the evidence shown to the local model."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd

from desk import detector
from desk.handlers import logs


class TestLogBriefing(unittest.TestCase):
    def test_scoring_is_independent_of_lab_labels(self):
        # Removing excluded labels used to drop entire rows and even change the host-minute features.
        rows = {column: [1] * 12 for column in detector._CSV_COLUMNS}
        rows.update({
            "Src IP": ["10.0.0.11"] * 12,
            "Dst IP": ["10.0.0.12"] * 12,
            "Timestamp": ["2017-07-05 14:00:00"] * 12,
            "Label": ["BENIGN"] * 7 + ["DoS"] + ["Unknown"] * 2 + ["DoS Attempted", "Heartbleed"],
        })
        frame = pd.DataFrame(rows)
        scorer = Mock(thresholds={"classifier": 11, "knn": 1})
        scorer.scores.side_effect = lambda df: (df["src_flows_1m"].to_numpy(), np.zeros(len(df)))
        scorer.scaler_all.side_effect = lambda x: x
        with TemporaryDirectory() as directory:
            path = Path(directory) / "logs.csv"
            frame.to_csv(path, index=False)
            labeled = detector.analyse(path, scorer)
            frame.drop(columns=["Label"]).to_csv(path, index=False)
            unlabeled = detector.analyse(path, scorer)
        self.assertEqual(labeled.connections, 12)
        self.assertEqual(labeled.alerts, unlabeled.alerts)
        self.assertEqual(labeled.incidents_total, 1)
        self.assertEqual([detector.public_card(c) for c in labeled.incidents], unlabeled.incidents)
        self.assertEqual(labeled.false_alarm_rate, 1.0)
        self.assertEqual(labeled.attack_alert_rate, 1.0)
        self.assertIsNone(unlabeled.false_alarm_rate)
        with patch.dict(logs._cache, {"key": labeled}), patch.object(logs.llm, "chat", return_value=("Review.", 1)) as model:
            result = logs.answer("key", b"", "logs.csv", "")
        prompt = model.call_args.args[1]
        self.assertNotIn("10.0.0.", prompt)
        self.assertNotIn("Benign", prompt)
        self.assertNotIn("_truth", prompt)
        self.assertIn("known normal connections", result.evidence[-1])

    def test_empty_queue_never_invents_an_incident(self):
        empty = detector.Report(connections=50, alerts=2, incidents=[], seconds=0)
        with patch.dict(logs._cache, {"key": empty}), patch.object(logs.llm, "chat") as model:
            result = logs.answer("key", b"", "logs.csv", "")
        model.assert_not_called()
        self.assertIn("50 connections, 2 alerts", result.text)
