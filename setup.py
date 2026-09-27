"""Create an isolated environment for the source checkout."""

from __future__ import annotations

import argparse
import subprocess
import sys
import venv
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"


def environment_python() -> Path:
    return VENV / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def main() -> int:
    parser = argparse.ArgumentParser(description="Set up AI Canvas in this checkout.")
    parser.add_argument("--maps", action="store_true", help="Install optional learned map processors (large PyTorch download).")
    args = parser.parse_args()
    if not ((3, 11) <= sys.version_info[:2] <= (3, 13)):
        parser.error("AI Canvas supports Python 3.11–3.13. Python 3.12 is recommended.")
    python = environment_python()
    if not python.is_file():
        print("Creating .venv...", flush=True)
        venv.EnvBuilder(with_pip=True).create(VENV)
    requirements = [ROOT / "requirements-core.txt"]
    if args.maps:
        requirements.append(ROOT / "requirements-maps.txt")
    for file in requirements:
        print(f"Installing {file.name}...", flush=True)
        subprocess.run([str(python), "-m", "pip", "install", "-r", str(file)], check=True)
    launcher = r".\.venv\Scripts\python.exe start.py" if sys.platform == "win32" else "./.venv/bin/python start.py"
    print(f"\nReady. Start AI Canvas with: {launcher}", flush=True)
    if not args.maps:
        print(f"For learned maps: {python} setup.py --maps", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as error:
        raise SystemExit(f"Setup stopped because pip exited with code {error.returncode}. The existing .venv was kept; retry after checking the error above.") from error
