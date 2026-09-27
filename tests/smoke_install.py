"""Exercise a fresh core install without touching a real user's projects."""

from __future__ import annotations

import base64
import io
import json
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = ROOT / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def request(url: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers), timeout=5) as response:
        return json.load(response)


def main() -> None:
    if not VENV_PYTHON.is_file():
        raise SystemExit("Run python setup.py first.")
    with tempfile.TemporaryDirectory(prefix="ai-canvas-smoke-") as temporary:
        root = Path(temporary)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        server = subprocess.Popen(
            [str(VENV_PYTHON), str(ROOT / "prototype" / "server.py"), "--port", str(port),
             "--mock-ai", "--projects-dir", str(root / "projects"), "--settings-file", str(root / "settings.json")],
            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
        try:
            base = f"http://127.0.0.1:{port}"
            for _ in range(100):
                if server.poll() is not None:
                    raise RuntimeError(f"Server exited: {server.stderr.read().decode(errors='replace')[-1000:]}")
                try:
                    request(f"{base}/api/health")
                    break
                except (OSError, urllib.error.HTTPError):
                    time.sleep(0.1)
            else:
                raise RuntimeError("Local server did not become healthy.")
            for headers in ({"Host": f"untrusted.example:{port}"}, {"Origin": "http://untrusted.example"}):
                try:
                    urllib.request.urlopen(urllib.request.Request(f"{base}/api/health", headers=headers), timeout=5)
                except urllib.error.HTTPError as error:
                    assert error.code == 403, error.code
                else:
                    raise AssertionError("The local API accepted a non-local request.")
            project = request(f"{base}/api/projects", {"name": "Clean install smoke"})
            image = Image.new("RGB", (64, 48), "white")
            image.paste("black", (16, 12, 48, 36))
            output = io.BytesIO()
            image.save(output, format="PNG")
            maps = request(f"{base}/api/projects/{project['id']}/maps", {
                "imageBase64": base64.b64encode(output.getvalue()).decode("ascii"),
                "types": ["canny"], "sourceName": "fixture.png", "sourceAssetId": "fixture",
            })
            assert [(item["type"], item["width"], item["height"]) for item in maps["maps"]] == [("canny", 64, 48)]
            assert not maps["errors"]
            assert (root / "projects" / "Clean install smoke" / "project.json").is_file()
            print("Core install smoke passed: server, project storage, Canny, and map export.")
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)


if __name__ == "__main__":
    main()
