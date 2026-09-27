"""Check optional processors without downloading any model weights."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


root = Path(__file__).resolve().parents[1]
python = root / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
subprocess.run([
    str(python), "-c",
    "import matplotlib; import torch; from transformers import AutoImageProcessor, AutoModelForDepthEstimation; "
    "from controlnet_aux import HEDdetector, LineartDetector, NormalBaeDetector, OpenposeDetector; "
    "print('Optional map processors import successfully.')",
], check=True)
