"""Protocol checks for a user-supplied ComfyUI map workflow."""

import io
import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "prototype"))
from comfy_maps import generate_map, server_url, validate_workflow  # noqa: E402


WORKFLOW = {
    "1": {"class_type": "LoadImage", "inputs": {"image": "placeholder.png"}},
    "2": {"class_type": "PreviewImage", "inputs": {"images": ["1", 0]}},
}


class FakeComfyUI(BaseHTTPRequestHandler):
    uploaded = False
    submitted = None

    def log_message(self, *_args):
        pass

    def do_POST(self):  # noqa: N802
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        if self.path == "/upload/image":
            self.__class__.uploaded = b"image/png" in body and b"\x89PNG" in body
            result = {"name": "uploaded.png", "subfolder": "", "type": "input"}
        elif self.path == "/prompt":
            self.__class__.submitted = json.loads(body)
            result = {"prompt_id": "test-prompt"}
        else:
            self.send_error(404)
            return
        data = json.dumps(result).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802
        if self.path == "/history/test-prompt":
            data = json.dumps({"test-prompt": {"outputs": {"2": {"images": [
                {"filename": "map.png", "subfolder": "", "type": "temp"}
            ]}}}}).encode()
            content_type = "application/json"
        elif self.path.startswith("/view?"):
            output = io.BytesIO()
            Image.new("RGB", (48, 32), "black").save(output, format="PNG")
            data = output.getvalue()
            content_type = "image/png"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class ComfyMapTests(unittest.TestCase):
    def test_local_workflow_round_trip(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), FakeComfyUI)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            source = io.BytesIO()
            Image.new("RGB", (64, 40), "white").save(source, format="PNG")
            result = generate_map(source.getvalue(), {
                "type": "depth", "name": "My depth model", "serverUrl": f"http://127.0.0.1:{server.server_port}",
                "workflow": WORKFLOW, "inputNodeId": "1", "outputNodeId": "2",
            })
            self.assertTrue(FakeComfyUI.uploaded)
            self.assertEqual(FakeComfyUI.submitted["prompt"]["1"]["inputs"]["image"], "uploaded.png")
            self.assertEqual(WORKFLOW["1"]["inputs"]["image"], "placeholder.png")
            self.assertEqual((result["width"], result["height"]), (48, 32))
            self.assertEqual(result["engine"], "comfyui")
        finally:
            server.shutdown()
            server.server_close()

    def test_workflow_and_address_validation(self):
        with self.assertRaises(ValueError):
            server_url("https://example.com:8188")
        with self.assertRaises(ValueError):
            validate_workflow({"nodes": []}, "1", "2")


if __name__ == "__main__":
    unittest.main()
