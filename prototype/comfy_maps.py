"""Run user-selected ComfyUI API workflows for reference maps.

Only loopback ComfyUI servers are accepted. A workflow supplies its own model,
preprocessor, and settings; AI Canvas replaces one LoadImage input and reads one
image output without interpreting the rest of the graph.
"""

from __future__ import annotations

import base64
import copy
import io
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any


MAP_TYPES = ("canny", "lineart", "depth", "pose", "softedge", "normal", "scribble", "animal_pose")
MODEL_OUTPUTS = {"SaveImage", "PreviewImage"}
MAX_WORKFLOW_BYTES = 2 * 1024 * 1024
MAX_OUTPUT_BYTES = 32 * 1024 * 1024


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        raise ValueError("ComfyUI redirected to another server.")


def server_url(value: str) -> str:
    parsed = urllib.parse.urlparse(value.strip().rstrip("/"))
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment
            or not parsed.port):
        raise ValueError("Use a local ComfyUI address such as http://127.0.0.1:8188.")
    return parsed.geturl().rstrip("/")


def validate_workflow(workflow: Any, input_node_id: str, output_node_id: str) -> dict[str, Any]:
    if not isinstance(workflow, dict) or not workflow or len(workflow) > 500:
        raise ValueError("Choose a ComfyUI workflow exported in API format.")
    if len(json.dumps(workflow)) > MAX_WORKFLOW_BYTES:
        raise ValueError("The workflow is larger than 2 MB.")
    if any(not isinstance(node, dict) or not isinstance(node.get("class_type"), str)
           or not isinstance(node.get("inputs"), dict) for node in workflow.values()):
        raise ValueError("The workflow must contain API-format nodes with class_type and inputs.")
    source = workflow.get(input_node_id)
    output = workflow.get(output_node_id)
    if not source or source.get("class_type") != "LoadImage" or "image" not in source["inputs"]:
        raise ValueError("Select a LoadImage input node from the workflow.")
    if not output or output.get("class_type") not in MODEL_OUTPUTS:
        raise ValueError("Select a SaveImage or PreviewImage output node.")
    return workflow


def _request(base: str, route: str, data: bytes | None = None, content_type: str | None = None,
             timeout: float = 15, limit: int = MAX_OUTPUT_BYTES) -> bytes:
    headers = {"Accept": "application/json"}
    if content_type:
        headers["Content-Type"] = content_type
    request = urllib.request.Request(base + route, data=data, headers=headers)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            content = response.read(limit + 1)
    except urllib.error.HTTPError as error:
        detail = error.read(1200).decode("utf-8", errors="replace")
        try:
            detail = json.loads(detail).get("error", detail)
        except (ValueError, AttributeError):
            pass
        raise RuntimeError(f"ComfyUI rejected the workflow ({error.code}): {str(detail)[:500]}") from error
    except urllib.error.URLError as error:
        raise RuntimeError("Cannot reach local ComfyUI. Start it and check its address.") from error
    if len(content) > limit:
        raise ValueError("ComfyUI returned an image larger than 32 MB.")
    return content


def check_connection(base: str) -> None:
    _request(server_url(base), "/system_stats", timeout=3, limit=128 * 1024)


def generate_map(source_bytes: bytes, config: dict[str, Any]) -> dict[str, Any]:
    from PIL import Image, ImageOps

    base = server_url(str(config.get("serverUrl") or ""))
    workflow = validate_workflow(config.get("workflow"), str(config.get("inputNodeId") or ""),
                                 str(config.get("outputNodeId") or ""))
    with Image.open(io.BytesIO(source_bytes)) as source:
        source = ImageOps.exif_transpose(source).convert("RGB")
        if source.width * source.height > 32_000_000:
            raise ValueError("This image exceeds the 32 megapixel map limit.")
        source_file = io.BytesIO()
        source.save(source_file, format="PNG")
    boundary = "ai-canvas-" + uuid.uuid4().hex
    filename = "ai-canvas-" + uuid.uuid4().hex + ".png"
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{filename}\"\r\n"
            "Content-Type: image/png\r\n\r\n").encode() + source_file.getvalue() + (
            f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"type\"\r\n\r\ninput\r\n--{boundary}--\r\n").encode()
    uploaded = json.loads(_request(base, "/upload/image", body, f"multipart/form-data; boundary={boundary}"))
    saved_name = uploaded.get("name")
    if not isinstance(saved_name, str) or not saved_name:
        raise RuntimeError("ComfyUI did not accept the source image.")

    prompt = copy.deepcopy(workflow)
    prompt[str(config["inputNodeId"])]["inputs"]["image"] = saved_name
    queued = json.loads(_request(base, "/prompt", json.dumps({"prompt": prompt, "client_id": uuid.uuid4().hex}).encode(),
                                 "application/json"))
    prompt_id = queued.get("prompt_id")
    if not isinstance(prompt_id, str) or not prompt_id:
        raise RuntimeError(f"ComfyUI did not queue the workflow: {str(queued.get('error') or queued)[:400]}")
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        history = json.loads(_request(base, "/history/" + urllib.parse.quote(prompt_id), timeout=10, limit=2 * 1024 * 1024))
        result = history.get(prompt_id)
        if result:
            status = result.get("status") or {}
            if status.get("status_str") == "error":
                raise RuntimeError("ComfyUI workflow failed. Check its queue and node errors.")
            images = (result.get("outputs") or {}).get(str(config["outputNodeId"]), {}).get("images") or []
            if not images:
                raise RuntimeError("The selected ComfyUI output node produced no image.")
            image_info = images[0]
            query = urllib.parse.urlencode({
                "filename": image_info.get("filename", ""),
                "subfolder": image_info.get("subfolder", ""),
                "type": image_info.get("type", "output"),
            })
            output = _request(base, "/view?" + query)
            with Image.open(io.BytesIO(output)) as image:
                image.load()
                if image.width * image.height > 32_000_000:
                    raise ValueError("ComfyUI output exceeds the 32 megapixel map limit.")
                raw_data_url = None
                if image.mode == "I;16":
                    import numpy as np

                    raw_png = io.BytesIO()
                    image.save(raw_png, format="PNG")
                    raw_data_url = "data:image/png;base64," + base64.b64encode(raw_png.getvalue()).decode("ascii")
                    gray = np.asarray(image, dtype=np.float32)
                    gray = (gray - gray.min()) / max(float(gray.max() - gray.min()), 1e-6)
                    image = Image.fromarray((gray * 255).astype(np.uint8)).convert("RGB")
                else:
                    image = image.convert("RGB")
                width, height = image.size
                encoded = io.BytesIO()
                image.save(encoded, format="PNG")
            result = {"type": config["type"], "dataUrl": "data:image/png;base64," +
                      base64.b64encode(encoded.getvalue()).decode("ascii"), "width": width, "height": height,
                      "engine": "comfyui", "workflowName": config.get("name") or "ComfyUI workflow"}
            if raw_data_url:
                result["rawDataUrl"] = raw_data_url
            return result
        time.sleep(0.5)
    raise TimeoutError("ComfyUI did not finish within five minutes. Check its queue.")
