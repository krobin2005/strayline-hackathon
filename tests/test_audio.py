import io
import unittest
import wave
from unittest.mock import patch

import numpy as np

from desk.handlers import audio


def pcm(samples, rate=16000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as writer:
        writer.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        writer.writeframes(np.asarray(samples, dtype="<i2").tobytes())
    return buf.getvalue()


class AudioTest(unittest.TestCase):
    def test_late_speech_after_background_sounds_reaches_transcriber(self):
        recording = pcm(np.r_[np.zeros(160000), np.full(16000, 400)])
        def classify(inputs, top_k):
            if inputs["raw"].max() > 0:
                return [{"label": "Speech", "score": .4}]
            return [{"label": label, "score": .6} for label in ("Music", "Piano", "Keyboard")]
        with patch.object(audio, "classifier", return_value=classify), \
             patch.object(audio.llm, "chat", return_value=("Meet at noon.", 0)) as model:
            result = audio.answer(recording, "message.wav", "")
        model.assert_called_once()
        self.assertIn("Meet at noon.", result.text)

    def test_classifier_gets_native_sample_rate_for_direct_wav_upload(self):
        recording = pcm(np.arange(44100), rate=44100)
        def classify(inputs, top_k):
            self.assertEqual(inputs["sampling_rate"], 16000)
            self.assertEqual(len(inputs["raw"]), 16000)
            return [{"label": "Music", "score": .8}]
        with patch.object(audio, "classifier", return_value=classify):
            result = audio.answer(recording, "music.wav", "")
        self.assertIn("Music", result.text)

    def test_weak_labels_do_not_become_identifications(self):
        with patch.object(audio, "classifier", return_value=lambda *a, **k: [{"label": "Music", "score": .02}]):
            result = audio.answer(pcm(np.ones(16000)), "unclear.wav", "")
        self.assertNotIn("Music", result.text)
        self.assertIn("No confident", result.text)

    def test_empty_recording_rejected_before_model_runs(self):
        with patch.object(audio, "classifier") as classifier:
            with self.assertRaises(audio.AudioError):
                audio.answer(pcm([]), "empty.wav", "")
            classifier.assert_not_called()
