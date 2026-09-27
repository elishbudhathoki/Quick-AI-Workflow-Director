"""Desktop defaults keep user data outside the source checkout."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "prototype"))
import server  # noqa: E402


class StoragePathTests(unittest.TestCase):
    def test_windows_defaults_preserve_existing_locations(self):
        with patch.object(server.sys, "platform", "win32"), patch.object(server.Path, "home", return_value=Path("C:/Users/example")), patch.dict(server.os.environ, {"LOCALAPPDATA": "C:/Users/example/AppData/Local"}, clear=True):
            self.assertEqual(server.default_data_dir(), Path("C:/Users/example/AppData/Local/AI Canvas"))
            self.assertEqual(server.default_projects_dir(), Path("C:/Users/example/Documents/AI Canvas Projects"))

    def test_linux_falls_back_to_app_data_without_documents(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            with patch.object(server.sys, "platform", "linux"), patch.object(server.Path, "home", return_value=home), patch.dict(server.os.environ, {}, clear=True):
                self.assertEqual(server.default_data_dir(), home / ".local/share/ai-canvas")
                self.assertEqual(server.default_projects_dir(), home / ".local/share/ai-canvas/projects")


if __name__ == "__main__":
    unittest.main()
