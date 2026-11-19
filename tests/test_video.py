import base64
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from desk.handlers import video


class VideoEvidenceTests(unittest.TestCase):
    def test_displayed_evidence_matches_the_single_model_input(self):
        frames = [np.full((120, 160, 3), level, np.uint8) for level in (50, 100, 150)]
        with patch.object(video, "sample_frames", return_value=(frames, [0, 1, 2], 3)), \
             patch.object(video.llm, "chat", return_value=("It gets brighter.", 0.1)) as model:
            result = video.answer(b"", "example.mp4", "What changes?")
        sheet, = model.call_args.kwargs["media"]
        self.assertEqual(sheet, base64.b64decode(result.frame_sheet_jpeg))
        pixels = cv2.imdecode(np.frombuffer(sheet, np.uint8), cv2.IMREAD_GRAYSCALE)
        centers = [pixels[row * video.CELL_HEIGHT + video.CELL_HEIGHT // 2,
                          col * video.CELL_WIDTH + video.CELL_WIDTH // 2]
                   for row, col in [(0, 0), (0, 1), (1, 0), (1, 1)]]
        np.testing.assert_allclose(centers, [50, 100, 150, 0], atol=2)
