import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from settings import gemini_settings


class SettingsTests(unittest.TestCase):
    def test_dotenv_quotes_comments_and_process_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text(
                '# Local configuration\nexport GEMINI_API_KEY="test-key" # comment\n'
                "GEMINI_MODEL='gemini-test'\n", encoding="utf-8-sig")
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(gemini_settings("default", env_file), ("test-key", "gemini-test"))
            with patch.dict(os.environ, {"GEMINI_API_KEY": "", "GEMINI_MODEL": "override"}):
                self.assertEqual(gemini_settings("default", env_file), ("", "override"))

    def test_missing_file_defaults_and_malformed_lines_do_not_expose_values(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            env_file = Path(directory) / ".env"
            self.assertEqual(gemini_settings("default", env_file), ("", "default"))
            env_file.write_text('GEMINI_API_KEY="unclosed\nOTHER=value\nGEMINI_MODEL=\n')
            self.assertEqual(gemini_settings("default", env_file), ("", ""))


if __name__ == "__main__":
    unittest.main()
