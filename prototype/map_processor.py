"""Local derived-reference maps using OpenCV, Depth Anything, and ControlNet Aux.

The source image never leaves the local server. Learned detectors download their
published weights on first use and then use the local Hugging Face cache.
"""

from __future__ import annotations

import base64
import io
import threading
from typing import Any

MAP_TYPES = ("canny", "lineart", "depth", "pose", "softedge", "normal", "scribble", "animal_pose")
MODEL_REPOSITORY = "lllyasviel/Annotators"
DEPTH_MODEL = "depth-anything/Depth-Anything-V2-Small-hf"
_detectors: dict[str, Any] = {}
_model_lock = threading.RLock()


def _detector(kind: str) -> Any:
    with _model_lock:
        if kind not in _detectors:
            try:
                from controlnet_aux import HEDdetector, LineartDetector, NormalBaeDetector, OpenposeDetector
            except ImportError as error:
                raise RuntimeError(
                    "Learned map types need the optional map models. "
                    "Install requirements-maps.txt, then retry."
                ) from error
            classes = {
                "lineart": LineartDetector,
                "pose": OpenposeDetector,
                "softedge": HEDdetector,
                "scribble": HEDdetector,
                "normal": NormalBaeDetector,
            }
            if kind == "animal_pose":
                raise RuntimeError("Animal pose needs a ComfyUI AnimalPosePreprocessor workflow. Select My ComfyUI models and import its API workflow.")
            cache_key = "hed" if kind in {"softedge", "scribble"} else kind
            if cache_key not in _detectors:
                _detectors[cache_key] = classes[kind].from_pretrained(MODEL_REPOSITORY)
            return _detectors[cache_key]
        return _detectors[kind]


def _depth_map(source: Any) -> Any:
    try:
        import numpy as np
        import torch
        from PIL import Image
        from transformers import AutoImageProcessor, AutoModelForDepthEstimation
    except ImportError as error:
        raise RuntimeError("Install requirements-maps.txt to enable detailed depth maps.") from error
    with _model_lock:
        if "depth-v2" not in _detectors:
            try:
                processor = AutoImageProcessor.from_pretrained(DEPTH_MODEL, local_files_only=True)
                model = AutoModelForDepthEstimation.from_pretrained(DEPTH_MODEL, local_files_only=True).eval()
            except OSError:
                processor = AutoImageProcessor.from_pretrained(DEPTH_MODEL)
                model = AutoModelForDepthEstimation.from_pretrained(DEPTH_MODEL).eval()
            _detectors["depth-v2"] = (processor, model)
        processor, model = _detectors["depth-v2"]
        working = source.copy()
        working.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
        inputs = processor(images=working, size={"height": 644, "width": 644}, return_tensors="pt")
        with torch.inference_mode():
            outputs = model(**inputs)
            depth = processor.post_process_depth_estimation(
                outputs, target_sizes=[(source.height, source.width)]
            )[0]["predicted_depth"]
        depth = depth.detach().float().cpu().numpy()
        depth = (depth - depth.min()) / max(float(depth.max() - depth.min()), 1e-6)
        preview = Image.fromarray((depth * 255).clip(0, 255).astype(np.uint8)).convert("RGB")
        raw = Image.fromarray((depth * 65535).clip(0, 65535).astype(np.uint16))
        return preview, raw


def generate_maps(source_bytes: bytes, requested: list[str]) -> dict[str, Any]:
    if not source_bytes or len(source_bytes) > 24 * 1024 * 1024:
        raise ValueError("Choose an image smaller than 24 MB.")
    kinds = list(dict.fromkeys(requested))
    if not kinds or any(kind not in MAP_TYPES for kind in kinds):
        raise ValueError("Choose one or more supported map types.")
    try:
        from PIL import Image, ImageOps
    except ImportError as error:
        raise RuntimeError("Install requirements-maps.txt to enable image maps.") from error
    try:
        with Image.open(io.BytesIO(source_bytes)) as source:
            source = ImageOps.exif_transpose(source)
            source.load()
            if source.width * source.height > 32_000_000:
                raise ValueError("This image exceeds the 32 megapixel map limit.")
            original = source.convert("RGB")
    except (OSError, ValueError) as error:
        if isinstance(error, ValueError):
            raise
        raise ValueError("The source is not a readable image.") from error

    results: list[dict[str, Any]] = []
    errors: dict[str, str] = {}
    for kind in kinds:
        try:
            raw_depth = None
            if kind == "canny":
                try:
                    import cv2
                    import numpy as np
                except ImportError as error:
                    raise RuntimeError("Install requirements-maps.txt to enable Canny maps.") from error
                gray = cv2.cvtColor(np.asarray(original), cv2.COLOR_RGB2GRAY)
                # Gradient-based thresholds retain low-contrast edges that a
                # pixel-intensity median misses in bright product photographs.
                sx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
                sy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
                gradients = cv2.magnitude(sx, sy)
                nonzero = gradients[gradients > 0]
                upper = max(20.0, min(200.0, float(np.percentile(nonzero, 70)) * 0.45)) if nonzero.size else 60.0
                lower = max(5.0, upper * 0.38)
                image = Image.fromarray(cv2.Canny(gray, lower, upper, L2gradient=True)).convert("RGB")
            elif kind == "depth":
                image, raw_depth = _depth_map(original)
            else:
                # Keep inference bounded on CPU; the exported PNG still uses the
                # source dimensions. The annotators scale by their shorter side.
                working = original.copy()
                working.thumbnail((768, 768), Image.Resampling.LANCZOS)
                detector = _detector(kind)
                with _model_lock:
                    resolution = min(working.size)
                    options = {"include_body": True, "include_hand": True, "include_face": True} if kind == "pose" else {}
                    if kind == "scribble":
                        options["scribble"] = True
                    image = detector(working, detect_resolution=resolution, image_resolution=resolution, **options)
                if not isinstance(image, Image.Image):
                    image = Image.fromarray(image)
                image = image.convert("RGB")
                if kind == "pose" and image.getbbox() is None:
                    raise ValueError("No person was detected in this image.")
                if image.size != original.size:
                    image = image.resize(original.size, Image.Resampling.LANCZOS)
            output = io.BytesIO()
            image.save(output, format="PNG", optimize=True)
            result = {
                "type": kind,
                "dataUrl": "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii"),
                "width": image.width,
                "height": image.height,
            }
            if raw_depth is not None:
                raw_output = io.BytesIO()
                raw_depth.save(raw_output, format="PNG")
                result["rawDataUrl"] = "data:image/png;base64," + base64.b64encode(raw_output.getvalue()).decode("ascii")
            results.append(result)
        except Exception as error:  # Each selected map has independent feedback.
            errors[kind] = str(error)[:400] or "Map generation failed."
    return {"maps": results, "errors": errors}
