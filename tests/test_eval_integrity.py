"""Use invented examples to check scoring decisions without loading any models."""
import unittest

from desk.eval import score, word_error_rate


class ScoringTests(unittest.TestCase):
    def test_counts(self):
        item = {"modality": "video", "question": "How many lights remain?"}
        expected = {"reference_answer": "3"}
        for response, verdict in [
            ("Three.", "correct"), ("2", "wrong"), ("3 at first, 2 remain", "review"),
            ("3.3", "review"), ("not 3", "review"), ("two (p. 3)", "wrong")
        ]:
            with self.subTest(response=response):
                self.assertEqual(score(item, expected, response, {}), verdict)

    def test_partial_phrase(self):
        item = {"modality": "image", "question": "Which animal is in the photo?"}
        expected = {"reference_answer": "cat"}
        for response, verdict in [("a cat", "correct"), ("bobcat", "review"),
                                  ("This is not a cat.", "review")]:
            with self.subTest(response=response):
                self.assertEqual(score(item, expected, response, {}), verdict)

    def test_transcript_scoring_keeps_all_words(self):
        self.assertEqual(word_error_rate("a cat is on the mat", "the mat"), 4 / 6)
        self.assertEqual(word_error_rate("they’re ready", "Transcript: They're ready."), 0)
