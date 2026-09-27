"""Direct image-link imports keep the media local and validate the response."""

import io
import sys
import tempfile
import threading
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "prototype"))
from server import ProjectRepository  # noqa: E402


class ImageHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):  # noqa: N802
        if self.path == "/redirect.png":
            self.send_response(302)
            self.send_header("Location", "/photo.png")
            self.end_headers()
            return
        output = io.BytesIO()
        Image.new("RGB", (48, 32), "#567abc").save(output, "PNG")
        data = output.getvalue() if self.path == "/photo.png" else b"not an image"
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class ImageImportTests(unittest.TestCase):
    def test_direct_image_import_and_validation(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), ImageHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                repository = ProjectRepository(Path(directory))
                project_id = repository.create("Image test")["id"]
                base = f"http://127.0.0.1:{server.server_port}"
                with self.assertRaises(ValueError):
                    repository.validate_public_url(base + "/photo.png")
                with patch.object(repository, "validate_public_url", side_effect=urllib.parse.urlparse):
                    result = repository.import_image_url(project_id, base + "/photo.png")
                    self.assertEqual((result["width"], result["height"]), (48, 32))
                    self.assertTrue((repository.folder(project_id) / result["sourceFile"]).is_file())
                    repository.save(project_id, {"assets": [{"id": "image-test", "type": "image",
                        "src": result["src"], "sourceFile": result["sourceFile"]}]})
                    self.assertTrue(repository.load(project_id)["snapshot"]["assets"][0]["src"].startswith("data:image/png;base64,"))
                    with self.assertRaises(ValueError):
                        repository.import_image_url(project_id, base + "/redirect.png")
                    with self.assertRaises(ValueError):
                        repository.import_image_url(project_id, base + "/invalid.png")
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
