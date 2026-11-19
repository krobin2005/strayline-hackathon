import asyncio
import io
import unittest
from unittest.mock import patch

from fastapi import UploadFile

from desk import server


class UploadRetentionTests(unittest.TestCase):
    def test_repeated_uploads_evict_the_oldest_attachment(self):
        with patch.object(server, "_attachments", {}), patch.object(server, "MAX_STORED_BYTES", 6):
            ids = []
            for value in (b"abc", b"def", b"ghi"):
                item = asyncio.run(server.upload(UploadFile(filename="case.txt", file=io.BytesIO(value))))
                ids.append(item["id"])
            self.assertEqual(list(server._attachments), ids[1:])
