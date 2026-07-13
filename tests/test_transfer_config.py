import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from transfer_config import get_phone_access_token, phone_access_url


class TransferConfigTests(unittest.TestCase):
    def test_phone_access_token_is_persistent_and_not_exposed_in_path(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ, {"APPDATA": temp_dir}
        ):
            first = get_phone_access_token()
            second = get_phone_access_token()
            self.assertEqual(first, second)
            self.assertGreaterEqual(len(first), 32)

            parsed = urlparse(phone_access_url("192.168.1.10"))
            self.assertEqual(parsed.scheme, "http")
            self.assertEqual(parsed.netloc, "192.168.1.10:56789")
            self.assertEqual(parse_qs(parsed.query)["token"], [first])
            self.assertNotIn(first, parsed.path)

            token_files = list(
                (Path(temp_dir) / "VoiceInputAssistant").glob("phone-access-token.txt")
            )
            self.assertEqual(len(token_files), 1)


if __name__ == "__main__":
    unittest.main()
