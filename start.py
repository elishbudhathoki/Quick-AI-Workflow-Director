"""Launch the same local server on Windows, macOS, or Linux."""

from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PYTHON = ROOT / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def main() -> int:
    parser = argparse.ArgumentParser(description="Start the AI Canvas desktop source release.")
    parser.add_argument("--port", type=int, default=4173)
    parser.add_argument("--projects-dir", type=Path)
    parser.add_argument("--settings-file", type=Path)
    parser.add_argument("--mock-ai", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if not PYTHON.is_file():
        parser.error("Run 'python setup.py' first to create .venv.")
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535.")
    try:
        with socket.create_connection(("127.0.0.1", args.port), timeout=0.3):
            parser.error(f"Port {args.port} is already in use. Stop that server or choose --port.")
    except OSError:
        pass
    command = [str(PYTHON), str(ROOT / "prototype" / "server.py"), "--host", "127.0.0.1", "--port", str(args.port)]
    if args.projects_dir:
        command += ["--projects-dir", str(args.projects_dir)]
    if args.settings_file:
        command += ["--settings-file", str(args.settings_file)]
    if args.mock_ai:
        command.append("--mock-ai")
    child = subprocess.Popen(command, cwd=ROOT)
    try:
        if not args.no_browser:
            for _ in range(60):
                if child.poll() is not None:
                    break
                try:
                    with socket.create_connection(("127.0.0.1", args.port), timeout=0.2):
                        webbrowser.open(f"http://127.0.0.1:{args.port}/")
                        break
                except OSError:
                    time.sleep(0.1)
        return child.wait()
    except KeyboardInterrupt:
        return 0
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == "__main__":
    raise SystemExit(main())
