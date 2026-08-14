"""Local AI Canvas development server.

Serves the dependency-free prototype and provides a same-origin drafting API.
API keys are read from environment variables or a local app settings file. The
settings file lives outside project folders and is never exported with a project.
"""

from __future__ import annotations

import argparse
import base64
import ipaddress
import json
import mimetypes
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


STATIC_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL = "gpt-5.6-terra"
MAX_BODY_BYTES = 320 * 1024 * 1024
MAX_VIDEO_BYTES = 240 * 1024 * 1024
MAX_REFERENCES = 30


PROVIDERS: dict[str, dict[str, Any]] = {
    "openai": {
        "id": "openai",
        "name": "OpenAI",
        "environmentVariable": "OPENAI_API_KEY",
        "defaultModel": "gpt-5.6-terra",
        "models": [
            {"id": "gpt-5.6-terra", "name": "GPT-5.6 Terra", "note": "Balanced"},
            {"id": "gpt-5.6-sol", "name": "GPT-5.6 Sol", "note": "Highest quality"},
            {"id": "gpt-5.6-luna", "name": "GPT-5.6 Luna", "note": "Economical"},
        ],
    },
    "gemini": {
        "id": "gemini",
        "name": "Google Gemini",
        "environmentVariable": "GEMINI_API_KEY",
        "defaultModel": "gemini-3.6-flash",
        "models": [
            {"id": "gemini-3.6-flash", "name": "Gemini 3.6 Flash", "note": "Balanced"},
            {"id": "gemini-3.1-pro-preview", "name": "Gemini 3.1 Pro Preview", "note": "Quality"},
            {"id": "gemini-3.5-flash-lite", "name": "Gemini 3.5 Flash-Lite", "note": "Economical"},
        ],
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemoryCredentialStore:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def get(self, provider_id: str) -> str | None:
        return self.values.get(provider_id)

    def set(self, provider_id: str, secret: str) -> None:
        self.values[provider_id] = secret

    def delete(self, provider_id: str) -> None:
        self.values.pop(provider_id, None)


class JsonCredentialStore:
    """Simple app-level provider settings stored outside all project folders."""

    def __init__(self, settings_file: Path) -> None:
        self.path = settings_file.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schemaVersion": 1, "providers": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise OSError(f"Could not read AI Canvas settings: {error}") from error
        if not isinstance(data, dict) or not isinstance(data.get("providers", {}), dict):
            raise OSError("AI Canvas settings file has an invalid format.")
        return data

    def write(self, data: dict[str, Any]) -> None:
        data["schemaVersion"] = 1
        data["updatedAt"] = utc_now()
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def get(self, provider_id: str) -> str | None:
        provider = self.read().get("providers", {}).get(provider_id, {})
        return str(provider.get("apiKey") or "").strip() or None

    def set(self, provider_id: str, secret: str) -> None:
        data = self.read()
        providers = data.setdefault("providers", {})
        providers[provider_id] = {"apiKey": secret, "updatedAt": utc_now()}
        self.write(data)

    def delete(self, provider_id: str) -> None:
        data = self.read()
        data.setdefault("providers", {}).pop(provider_id, None)
        self.write(data)

    def get_preferences(self) -> dict[str, Any]:
        preferences = self.read().get("preferences", {})
        return {
            "copyPromptOnExport": bool(preferences.get("copyPromptOnExport", True)),
            "openFolderOnExport": bool(preferences.get("openFolderOnExport", True)),
            "lastActiveProjectId": str(preferences.get("lastActiveProjectId") or "") or None,
            "openProjectIds": [str(value) for value in preferences.get("openProjectIds", []) if isinstance(value, str)],
        }

    def set_preferences(self, preferences: dict[str, Any]) -> dict[str, Any]:
        data = self.read()
        current = data.setdefault("preferences", {})
        for key in ("copyPromptOnExport", "openFolderOnExport"):
            if key in preferences:
                current[key] = bool(preferences[key])
        if "lastActiveProjectId" in preferences:
            value = preferences.get("lastActiveProjectId")
            current["lastActiveProjectId"] = str(value) if value else None
        if "openProjectIds" in preferences:
            values = preferences.get("openProjectIds")
            if not isinstance(values, list):
                raise ValueError("Open project ids must be a list.")
            current["openProjectIds"] = [str(value) for value in values if isinstance(value, str)][:50]
        self.write(data)
        return self.get_preferences()


class ProjectRepository:
    PROJECT_ID = re.compile(r"^[a-z0-9][a-z0-9-]{2,80}$")
    WINDOWS_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def slug(value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:48]
        return slug or "untitled-project"

    @classmethod
    def clean_name(cls, value: str) -> str:
        name = re.sub(r"\s+", " ", value).strip()
        name = re.sub(r'[<>:"/\\|?*]', "-", name).rstrip(" .")[:80] or "Untitled project"
        if name.lower() in cls.WINDOWS_RESERVED:
            name = f"{name} project"
        return name

    def available_folder(self, name: str, current: Path | None = None) -> Path:
        base = self.clean_name(name)
        candidate = (self.root / base).resolve()
        index = 2
        while candidate.exists() and (current is None or candidate != current.resolve()):
            candidate = (self.root / f"{base} {index}").resolve()
            index += 1
        if self.root not in candidate.parents:
            raise ValueError("Project path escapes the project root.")
        return candidate

    def folder(self, project_id: str) -> Path:
        if not self.PROJECT_ID.fullmatch(project_id):
            raise ValueError("Invalid project id.")
        legacy = (self.root / project_id).resolve()
        if legacy.exists() and (legacy / "project.json").exists():
            return legacy
        for record_file in self.root.glob("*/project.json"):
            try:
                record = json.loads(record_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if record.get("id") == project_id:
                return record_file.parent.resolve()
        raise FileNotFoundError("Project not found.")

    def create(self, name: str) -> dict[str, Any]:
        folder = self.available_folder(name)
        clean_name = folder.name
        project_id = f"project-{secrets.token_hex(6)}"
        folder.mkdir(parents=True)
        (folder / "media").mkdir()
        (folder / "exports").mkdir()
        record = {
            "schemaVersion": 1,
            "id": project_id,
            "name": clean_name,
            "createdAt": utc_now(),
            "updatedAt": utc_now(),
            "snapshot": None,
        }
        self.write_record(folder, record)
        return self.summary(record, folder)

    @staticmethod
    def write_record(folder: Path, record: dict[str, Any]) -> None:
        temporary = folder / "project.json.tmp"
        temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(folder / "project.json")

    @staticmethod
    def summary(record: dict[str, Any], folder: Path) -> dict[str, Any]:
        snapshot = record.get("snapshot") or {}
        return {
            "id": record["id"],
            "name": record["name"],
            "createdAt": record.get("createdAt"),
            "updatedAt": record.get("updatedAt"),
            "assetCount": len(snapshot.get("assets") or []),
            "folder": str(folder),
        }

    def list(self) -> list[dict[str, Any]]:
        projects = []
        for file in self.root.glob("*/project.json"):
            try:
                record = json.loads(file.read_text(encoding="utf-8"))
                projects.append(self.summary(record, file.parent))
            except (OSError, json.JSONDecodeError, KeyError):
                continue
        return sorted(projects, key=lambda item: item.get("updatedAt") or "", reverse=True)

    @staticmethod
    def parse_data_url(value: str) -> tuple[str, bytes]:
        match = re.fullmatch(r"data:([^;,]+);base64,(.+)", value, re.DOTALL)
        if not match:
            raise ValueError("Only base64 media data URLs can be saved in a project.")
        return match.group(1), base64.b64decode(match.group(2), validate=True)

    def save(self, project_id: str, snapshot: dict[str, Any]) -> dict[str, Any]:
        folder = self.folder(project_id)
        record_file = folder / "project.json"
        if not record_file.exists():
            raise FileNotFoundError("Project not found.")
        record = json.loads(record_file.read_text(encoding="utf-8"))
        stored_snapshot = json.loads(json.dumps(snapshot))
        media_folder = folder / "media"
        media_folder.mkdir(exist_ok=True)
        for asset in stored_snapshot.get("assets") or []:
            source = str(asset.get("src") or "")
            if not source.startswith("data:"):
                continue
            mime_type, data = self.parse_data_url(source)
            extension = mimetypes.guess_extension(mime_type) or ".bin"
            safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", str(asset.get("id") or secrets.token_hex(4)))
            filename = f"{safe_id}{extension}"
            (media_folder / filename).write_bytes(data)
            asset["sourceFile"] = f"media/{filename}"
            asset.pop("src", None)
        record["snapshot"] = stored_snapshot
        record["updatedAt"] = utc_now()
        self.write_record(folder, record)
        return self.summary(record, folder)

    def rename(self, project_id: str, name: str) -> dict[str, Any]:
        folder = self.folder(project_id)
        record_file = folder / "project.json"
        if not record_file.exists():
            raise FileNotFoundError("Project not found.")
        if not name.strip():
            raise ValueError("Project name cannot be empty.")
        target = self.available_folder(name, current=folder)
        clean_name = target.name
        record = json.loads(record_file.read_text(encoding="utf-8"))
        record["name"] = clean_name
        record["updatedAt"] = utc_now()
        self.write_record(folder, record)
        if target != folder:
            folder.rename(target)
            folder = target
        return self.summary(record, folder)

    def duplicate(self, project_id: str) -> dict[str, Any]:
        source_folder = self.folder(project_id)
        source_record = json.loads((source_folder / "project.json").read_text(encoding="utf-8"))
        duplicate = self.create(f"{source_record.get('name') or 'Untitled project'} copy")
        target_folder = self.folder(str(duplicate["id"]))
        source_media = source_folder / "media"
        target_media = target_folder / "media"
        if source_media.exists():
            for source_file in source_media.iterdir():
                if source_file.is_file():
                    shutil.copy2(source_file, target_media / source_file.name)
        target_record = json.loads((target_folder / "project.json").read_text(encoding="utf-8"))
        target_record["snapshot"] = json.loads(json.dumps(source_record.get("snapshot") or {}))
        target_record["updatedAt"] = utc_now()
        self.write_record(target_folder, target_record)
        return self.summary(target_record, target_folder)

    def delete(self, project_id: str) -> str:
        folder = self.folder(project_id).resolve()
        if self.root not in folder.parents or folder == self.root:
            raise ValueError("Project deletion target is outside the project root.")
        shutil.rmtree(folder)
        return str(folder)

    @staticmethod
    def validate_public_url(value: str) -> urllib.parse.ParseResult:
        parsed = urllib.parse.urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Paste a valid http or https video URL.")
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port or 443)}
        except socket.gaierror as error:
            raise ValueError(f"Video host could not be resolved: {error}") from error
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                raise ValueError("Local or private-network video URLs are not allowed.")
        return parsed

    def import_video_url(self, project_id: str, url: str) -> dict[str, Any]:
        folder = self.folder(project_id)
        parsed = self.validate_public_url(url)
        request = urllib.request.Request(url, headers={"User-Agent": "AI Canvas/0.4"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                final_url = response.geturl()
                self.validate_public_url(final_url)
                mime_type = response.headers.get_content_type().lower()
                content_length = int(response.headers.get("Content-Length") or 0)
                extension = Path(urllib.parse.urlparse(final_url).path).suffix.lower()
                allowed_extensions = {".mp4", ".webm", ".mov", ".m4v", ".mkv"}
                if not mime_type.startswith("video/") and extension not in allowed_extensions:
                    raise ValueError("This URL is not a direct video file. Paste a direct .mp4, .webm, .mov, or .mkv link.")
                if content_length > MAX_VIDEO_BYTES:
                    raise ValueError(f"Video is larger than the {MAX_VIDEO_BYTES // (1024 * 1024)} MB local import limit.")
                chunks = []
                total = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_VIDEO_BYTES:
                        raise ValueError(f"Video exceeded the {MAX_VIDEO_BYTES // (1024 * 1024)} MB local import limit.")
                    chunks.append(chunk)
        except urllib.error.HTTPError as error:
            raise ValueError(f"Video download failed ({error.code} {error.reason}).") from error
        except urllib.error.URLError as error:
            raise ValueError(f"Video download failed: {error.reason}") from error
        extension = extension if extension in allowed_extensions else (mimetypes.guess_extension(mime_type) or ".mp4")
        raw_name = Path(urllib.parse.unquote(parsed.path)).stem or "Downloaded video"
        display_name = self.clean_name(raw_name) + extension
        safe_stem = re.sub(r"[^a-zA-Z0-9_-]", "-", raw_name).strip("-")[:42] or "video"
        filename = f"video-{safe_stem}-{secrets.token_hex(4)}{extension}"
        relative = f"media/{filename}"
        (folder / relative).write_bytes(b"".join(chunks))
        return {
            "name": display_name,
            "mimeType": mime_type if mime_type.startswith("video/") else (mimetypes.guess_type(filename)[0] or "video/mp4"),
            "sourceFile": relative,
            "src": f"/api/projects/{project_id}/media/{urllib.parse.quote(filename)}",
            "size": total,
        }

    def media_file(self, project_id: str, filename: str) -> Path:
        folder = self.folder(project_id)
        media_folder = (folder / "media").resolve()
        path = (media_folder / filename).resolve()
        if media_folder not in path.parents or path.parent != media_folder:
            raise ValueError("Invalid media filename.")
        if not path.exists() or not path.is_file():
            raise FileNotFoundError("Project media file not found.")
        return path

    def export(self, project_id: str, files: list[dict[str, Any]], open_folder: bool = False) -> dict[str, Any]:
        folder = self.folder(project_id)
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        export_folder = folder / "exports" / stamp
        suffix = 2
        while export_folder.exists():
            export_folder = folder / "exports" / f"{stamp}_{suffix}"
            suffix += 1
        decoded: dict[str, bytes] = {}
        for item in files:
            name = str(item.get("name") or "")
            if not name or Path(name).name != name or name in {".", ".."}:
                raise ValueError("Export contains an invalid filename.")
            if name in decoded:
                raise ValueError(f"Export contains duplicate filename: {name}")
            encoded = str(item.get("base64") or "")
            decoded[name] = base64.b64decode(encoded, validate=True)
        if "prompt.md" not in decoded or "manifest.json" not in decoded:
            raise ValueError("Export must contain prompt.md and manifest.json.")
        try:
            manifest = json.loads(decoded["manifest.json"].decode("utf-8"))
            prompt = decoded["prompt.md"].decode("utf-8")
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError(f"Export prompt or manifest is invalid: {error}") from error
        references = manifest.get("references")
        if not isinstance(references, list) or not references:
            raise ValueError("Export manifest must contain at least one reference.")
        reference_names = [str(reference.get("filename") or "") for reference in references if isinstance(reference, dict)]
        if len(reference_names) != len(references) or len(set(reference_names)) != len(reference_names):
            raise ValueError("Export manifest contains invalid or duplicate reference filenames.")
        expected_names = {"prompt.md", "manifest.json", *reference_names}
        if set(decoded) != expected_names:
            missing = sorted(expected_names - set(decoded))
            extra = sorted(set(decoded) - expected_names)
            raise ValueError(f"Export file set does not match its manifest. Missing: {missing or 'none'}; extra: {extra or 'none'}.")
        missing_citations = [name for name in reference_names if name not in prompt]
        if missing_citations:
            raise ValueError(f"Export prompt does not cite: {', '.join(missing_citations)}")
        unknown_citations = sorted(
            set(re.findall(r"\b(?:R\d{2,}[A-Z]+\.png|V\d{2,}\.(?:mp4|webm|mov|mkv))\b", prompt))
            - set(reference_names)
        )
        if unknown_citations:
            raise ValueError(f"Export prompt cites unknown crops: {', '.join(unknown_citations)}")
        if bool((manifest.get("draft") or {}).get("stale")):
            raise ValueError("Export prompt is stale. Regenerate it before exporting.")
        temporary_folder = export_folder.parent / f".{export_folder.name}.tmp-{secrets.token_hex(4)}"
        temporary_folder.mkdir(parents=True)
        try:
            for name, data in decoded.items():
                (temporary_folder / name).write_bytes(data)
            temporary_folder.replace(export_folder)
        except Exception:
            shutil.rmtree(temporary_folder, ignore_errors=True)
            raise
        folder_opened = False
        open_error = None
        if open_folder and sys.platform == "win32":
            try:
                subprocess.Popen(["explorer.exe", str(export_folder)])
                folder_opened = True
            except OSError as error:
                open_error = str(error)
        return {
            "folder": str(export_folder),
            "fileCount": len(files),
            "folderOpened": folder_opened,
            "openError": open_error,
        }

    def load(self, project_id: str) -> dict[str, Any]:
        folder = self.folder(project_id)
        record_file = folder / "project.json"
        if not record_file.exists():
            raise FileNotFoundError("Project not found.")
        record = json.loads(record_file.read_text(encoding="utf-8"))
        snapshot = json.loads(json.dumps(record.get("snapshot") or {}))
        for asset in snapshot.get("assets") or []:
            relative = asset.get("sourceFile")
            if not relative:
                continue
            source_file = (folder / relative).resolve()
            if folder not in source_file.parents:
                asset["src"] = ""
                asset["mediaError"] = f"Invalid media path: {relative}"
                continue
            if not source_file.exists():
                asset["src"] = ""
                asset["mediaError"] = f"Missing media file: {relative}"
                continue
            try:
                mime_type = mimetypes.guess_type(source_file.name)[0] or "application/octet-stream"
                if str(asset.get("type") or "image") == "video" or mime_type.startswith("video/"):
                    filename = urllib.parse.quote(source_file.name)
                    asset["src"] = f"/api/projects/{project_id}/media/{filename}"
                    asset["mimeType"] = mime_type
                else:
                    asset["src"] = f"data:{mime_type};base64,{base64.b64encode(source_file.read_bytes()).decode('ascii')}"
                asset.pop("mediaError", None)
            except OSError as error:
                asset["src"] = ""
                asset["mediaError"] = f"Could not read {relative}: {error}"
        return {**self.summary(record, folder), "snapshot": snapshot}


OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "finalPrompt": {"type": "string"},
        "references": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string"},
                    "description": {"type": "string"},
                    "use": {"type": "string"},
                    "avoid": {"type": "string"},
                    "observations": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": [
                    "filename",
                    "description",
                    "use",
                    "avoid",
                    "observations",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["summary", "finalPrompt", "references"],
    "additionalProperties": False,
}


SYSTEM_INSTRUCTIONS = """You are the visual-reference compiler inside AI Canvas.
Analyze every attached image crop or sampled-video contact sheet and draft one detailed generation prompt.

Hard requirements:
- Treat each attachment as authoritative only for the user's instruction paired with its exact filename.
- A filename beginning with V is a whole-video reference represented to you by a sampled contact sheet. Describe only temporal or visual qualities supported by those samples and preserve the V filename in the final prompt.
- Never claim to use an original source image; only the exported references named by the user are available downstream.
- Describe visible, transferable visual properties precisely. For style references, discuss rendering, linework, shape language, texture, and finish without identifying or imitating a living artist.
- Preserve exclusions such as 'without logo' in both the reference analysis and final prompt.
- Do not invent details that are not visible in a crop.
- The final prompt must explicitly cite every filename near the visual instruction it controls.
- Follow the user's drafting-format instructions when they do not conflict with these rules.
- Return only the requested structured result. Do not generate an image or call another tool.
"""


def json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def provider_network_error(provider_name: str, error: urllib.error.URLError) -> RuntimeError:
    reason = getattr(error, "reason", None)
    detail = str(reason or error)
    return RuntimeError(
        f"AI Canvas reached its local server, but the server could not contact {provider_name}. "
        f"Check the internet connection, firewall, or proxy and try again. ({detail})"
    )


def validate_payload(payload: Any) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(payload, dict):
        return None, "Request body must be a JSON object."
    references = payload.get("references")
    if not isinstance(references, list) or not references:
        return None, "At least one annotated reference crop is required."
    if len(references) > MAX_REFERENCES:
        return None, f"A maximum of {MAX_REFERENCES} crops can be analyzed at once."
    required = ("filename", "instruction", "imageDataUrl")
    for index, reference in enumerate(references):
        if not isinstance(reference, dict):
            return None, f"Reference {index + 1} must be an object."
        missing = [key for key in required if not str(reference.get(key, "")).strip()]
        if missing:
            return None, f"Reference {index + 1} is missing: {', '.join(missing)}."
        image_url = str(reference["imageDataUrl"])
        if not image_url.startswith("data:image/"):
            return None, f"Reference {index + 1} must contain a local image data URL."
    return payload, None


def build_openai_request(payload: dict[str, Any]) -> dict[str, Any]:
    objective = str(payload.get("objective", "")).strip()
    drafting_instructions = str(payload.get("draftingInstructions", "")).strip()
    content: list[dict[str, Any]] = [
        {
            "type": "input_text",
            "text": (
                "CREATIVE OBJECTIVE\n"
                f"{objective or '[No objective supplied]'}\n\n"
                "DRAFTING FORMAT INSTRUCTIONS\n"
                f"{drafting_instructions or '[Use a clear production-ready structure]'}\n\n"
                "REFERENCE CROPS\n"
                "Each metadata block is immediately followed by its matching image crop."
            ),
        }
    ]
    for reference in payload["references"]:
        content.append(
            {
                "type": "input_text",
                "text": (
                    f"Filename: {reference['filename']}\n"
                    f"User instruction: {reference['instruction']}"
                ),
            }
        )
        content.append(
            {
                "type": "input_image",
                "image_url": reference["imageDataUrl"],
                "detail": str(payload.get("imageDetail", "auto")),
            }
        )
    return {
        "model": str(payload.get("model") or DEFAULT_MODEL),
        "store": False,
        "instructions": SYSTEM_INSTRUCTIONS,
        "input": [{"role": "user", "content": content}],
        "reasoning": {"effort": "low"},
        "max_output_tokens": 6000,
        "text": {
            "verbosity": "medium",
            "format": {
                "type": "json_schema",
                "name": "ai_canvas_draft",
                "strict": True,
                "schema": OUTPUT_SCHEMA,
            },
        },
    }


def extract_output_text(response: dict[str, Any]) -> str:
    for output in response.get("output", []):
        if output.get("type") != "message":
            continue
        for content in output.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                return str(content["text"])
    raise ValueError("The model response did not contain output text.")


def call_openai(payload: dict[str, Any], api_key: str) -> dict[str, Any]:
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json_bytes(build_openai_request(payload)),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        try:
            detail = json.loads(error.read().decode("utf-8"))
            message = detail.get("error", {}).get("message") or str(error)
        except (json.JSONDecodeError, UnicodeDecodeError):
            message = str(error)
        raise RuntimeError(message) from error
    except urllib.error.URLError as error:
        raise provider_network_error("OpenAI", error) from error
    parsed = json.loads(extract_output_text(raw))
    parsed["model"] = raw.get("model") or payload.get("model") or DEFAULT_MODEL
    parsed["responseId"] = raw.get("id")
    parsed["usage"] = raw.get("usage")
    return parsed


def build_gemini_request(payload: dict[str, Any]) -> dict[str, Any]:
    objective = str(payload.get("objective", "")).strip()
    drafting_instructions = str(payload.get("draftingInstructions", "")).strip()
    input_parts: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": (
                "CREATIVE OBJECTIVE\n"
                f"{objective or '[No objective supplied]'}\n\n"
                "DRAFTING FORMAT INSTRUCTIONS\n"
                f"{drafting_instructions or '[Use a clear production-ready structure]'}\n\n"
                "REFERENCE CROPS\n"
                "Each metadata block is immediately followed by its matching image crop."
            ),
        }
    ]
    resolution = {
        "low": "low",
        "high": "high",
        "original": "high",
        "auto": "unspecified",
    }.get(str(payload.get("imageDetail", "auto")), "unspecified")
    for reference in payload["references"]:
        mime_type, encoded = ProjectRepository.parse_data_url(str(reference["imageDataUrl"]))
        input_parts.append(
            {
                "type": "text",
                "text": (
                    f"Filename: {reference['filename']}\n"
                    f"User instruction: {reference['instruction']}"
                ),
            }
        )
        input_parts.append(
            {
                "type": "image",
                "data": base64.b64encode(encoded).decode("ascii"),
                "mime_type": mime_type,
                "resolution": resolution,
            }
        )
    return {
        "model": str(payload.get("model") or PROVIDERS["gemini"]["defaultModel"]),
        "store": False,
        "system_instruction": SYSTEM_INSTRUCTIONS,
        "input": input_parts,
        "response_format": {
            "type": "text",
            "mime_type": "application/json",
            "schema": OUTPUT_SCHEMA,
        },
    }


def find_gemini_output_text(value: Any) -> str | None:
    if isinstance(value, dict):
        direct = value.get("output_text")
        if isinstance(direct, str) and direct.strip():
            return direct
        if value.get("type") in {"text", "output_text"} and isinstance(value.get("text"), str):
            return str(value["text"])
        for key in ("outputs", "steps", "content", "parts"):
            found = find_gemini_output_text(value.get(key))
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = find_gemini_output_text(item)
            if found:
                return found
    return None


def call_gemini(payload: dict[str, Any], api_key: str) -> dict[str, Any]:
    request = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/interactions",
        data=json_bytes(build_gemini_request(payload)),
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        try:
            detail = json.loads(error.read().decode("utf-8"))
            message = detail.get("error", {}).get("message") or str(error)
        except (json.JSONDecodeError, UnicodeDecodeError):
            message = str(error)
        raise RuntimeError(message) from error
    except urllib.error.URLError as error:
        raise provider_network_error("Google Gemini", error) from error
    output_text = find_gemini_output_text(raw)
    if not output_text:
        raise ValueError("The Gemini response did not contain output text.")
    parsed = json.loads(output_text)
    parsed["model"] = raw.get("model") or payload.get("model") or PROVIDERS["gemini"]["defaultModel"]
    parsed["responseId"] = raw.get("id")
    parsed["usage"] = raw.get("usage_metadata") or raw.get("usage")
    return parsed


def validate_provider_credential(provider_id: str, api_key: str) -> None:
    if provider_id == "openai":
        request = urllib.request.Request(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
    elif provider_id == "gemini":
        request = urllib.request.Request(
            "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1",
            headers={"x-goog-api-key": api_key},
        )
    else:
        raise ValueError("Unsupported provider.")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status >= 400:
                raise RuntimeError(f"Provider returned status {response.status}.")
    except urllib.error.HTTPError as error:
        try:
            detail = json.loads(error.read().decode("utf-8"))
            message = detail.get("error", {}).get("message") or str(error)
        except (json.JSONDecodeError, UnicodeDecodeError):
            message = str(error)
        raise RuntimeError(message) from error
    except urllib.error.URLError as error:
        provider_name = str(PROVIDERS[provider_id]["name"])
        raise provider_network_error(provider_name, error) from error


def mock_draft(payload: dict[str, Any]) -> dict[str, Any]:
    references = []
    reference_lines = []
    for reference in payload["references"]:
        avoid = ""
        instruction = str(reference["instruction"])
        lowered = instruction.lower()
        if " without " in lowered:
            avoid = "Do not include " + instruction[lowered.index(" without ") + 9 :].strip(" .") + "."
        description = f"Vision mock: visible properties are grounded in {reference['filename']}."
        use = f"Apply this instruction to {reference['filename']}: {instruction}"
        references.append(
            {
                "filename": reference["filename"],
                "description": description,
                "use": use,
                "avoid": avoid,
                "observations": ["Mock mode does not perform image recognition."],
            }
        )
        line = f"- {use} {avoid}".strip()
        reference_lines.append(line)
    objective = str(payload.get("objective") or "Create the requested image.").strip()
    formatting = str(payload.get("draftingInstructions") or "").strip()
    final_prompt = "\n".join(
        [
            objective,
            "",
            "REFERENCE APPLICATION",
            *reference_lines,
            *( ["", "FORMAT", formatting] if formatting else [] ),
        ]
    )
    return {
        "summary": "End-to-end mock response; no crops were transmitted or visually analyzed.",
        "finalPrompt": final_prompt,
        "references": references,
        "model": "mock-local",
        "responseId": None,
        "usage": None,
    }


class VideoJobManager:
    """Small local job runner for permitted public video-page downloads."""

    def __init__(self, projects: ProjectRepository) -> None:
        self.projects = projects
        self.jobs: dict[str, dict[str, Any]] = {}
        self.lock = threading.RLock()

    def create(self, project_id: str, url: str) -> dict[str, Any]:
        self.projects.folder(project_id)
        self.projects.validate_public_url(url)
        job = {"id": f"video-job-{secrets.token_hex(6)}", "projectId": project_id, "url": url,
               "state": "resolving", "progress": 0, "createdAt": utc_now(), "updatedAt": utc_now(), "error": None}
        with self.lock:
            self.jobs[job["id"]] = job
        threading.Thread(target=self.run, args=(job["id"],), daemon=True).start()
        return dict(job)

    def get(self, project_id: str, job_id: str) -> dict[str, Any]:
        with self.lock:
            job = self.jobs.get(job_id)
            if not job or job["projectId"] != project_id:
                raise FileNotFoundError("Video job not found.")
            return dict(job)

    def cancel(self, project_id: str, job_id: str) -> dict[str, Any]:
        with self.lock:
            job = self.get(project_id, job_id)
            if job["state"] in {"ready", "failed", "cancelled"}:
                return job
            self.jobs[job_id].update(state="cancelled", updatedAt=utc_now())
            return dict(self.jobs[job_id])

    def run(self, job_id: str) -> None:
        try:
            import yt_dlp
            with self.lock:
                job = self.jobs[job_id]
                url, project_id = job["url"], job["projectId"]
                job.update(state="downloading", progress=1, updatedAt=utc_now())
            folder = self.projects.folder(project_id)
            temporary = folder / "media" / ".downloads"
            temporary.mkdir(exist_ok=True)
            # Let each extractor choose its best public format. Filtering on a
            # reported filesize rejects Pinterest streams that omit that field;
            # the post-download size check below remains the hard safety limit.
            options = {"outtmpl": str(temporary / "%(id)s.%(ext)s"), "noplaylist": True,
                       "max_filesize": MAX_VIDEO_BYTES, "quiet": True, "no_warnings": True}
            node = shutil.which("node")
            if node:
                # YouTube increasingly requires its player JavaScript to be
                # interpreted. Enable the user's installed Node runtime rather
                # than attempting to imitate a logged-in browser session.
                options["js_runtimes"] = {"node": {"path": node}}
            # YouTube's default anonymous web client can report public Shorts
            # as unavailable. The official Android client exposes the same
            # public, non-DRM stream without cookies or authenticated access.
            if "youtube.com" in urllib.parse.urlparse(url).hostname.lower() or "youtu.be" in urllib.parse.urlparse(url).hostname.lower():
                options["extractor_args"] = {"youtube": {"player_client": ["android"]}}
            with yt_dlp.YoutubeDL(options) as downloader:
                info = downloader.extract_info(url, download=True)
            with self.lock:
                if self.jobs[job_id]["state"] == "cancelled": return
            filename = Path(downloader.prepare_filename(info))
            if not filename.exists(): raise RuntimeError("Downloader did not produce a local video file.")
            if filename.stat().st_size > MAX_VIDEO_BYTES: raise RuntimeError("Video exceeded the 240 MB local import limit.")
            target_name = f"video-{secrets.token_hex(8)}{filename.suffix.lower() or '.mp4'}"
            target = folder / "media" / target_name
            filename.replace(target)
            result = {"name": self.projects.clean_name(str(info.get("title") or "Downloaded video")) + target.suffix,
                      "mimeType": mimetypes.guess_type(target.name)[0] or "video/mp4", "sourceFile": f"media/{target_name}",
                      "src": f"/api/projects/{project_id}/media/{urllib.parse.quote(target_name)}", "size": target.stat().st_size,
                      "title": info.get("title"), "duration": info.get("duration"), "extractor": info.get("extractor")}
            with self.lock: self.jobs[job_id].update(state="ready", progress=100, result=result, updatedAt=utc_now())
        except Exception as error:
            with self.lock: self.jobs[job_id].update(state="failed", error=str(error), updatedAt=utc_now())


class CanvasRequestHandler(SimpleHTTPRequestHandler):
    server_version = "AICanvasLocal/0.3"

    @property
    def mock_ai(self) -> bool:
        return bool(getattr(self.server, "mock_ai", False))

    @property
    def credential_store(self) -> MemoryCredentialStore | JsonCredentialStore:
        return getattr(self.server, "credential_store")

    @property
    def projects(self) -> ProjectRepository:
        return getattr(self.server, "project_repository")

    @property
    def video_jobs(self) -> VideoJobManager:
        return getattr(self.server, "video_jobs")

    def send_json(self, status: int, value: Any) -> None:
        body = json_bytes(value)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_json_body(self) -> dict[str, Any] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY_BYTES:
            self.send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "Invalid request size."})
            return None
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Request body must be valid JSON."})
            return None
        if not isinstance(body, dict):
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Request body must be a JSON object."})
            return None
        return body

    def send_project_media(self, project_id: str, filename: str) -> None:
        try:
            path = self.projects.media_file(project_id, urllib.parse.unquote(filename))
        except FileNotFoundError as error:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": str(error)})
            return
        except ValueError as error:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            return
        size = path.stat().st_size
        start = 0
        end = max(0, size - 1)
        status = HTTPStatus.OK
        range_header = self.headers.get("Range") or ""
        match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header)
        if match and size:
            if match.group(1):
                start = int(match.group(1))
                end = min(end, int(match.group(2))) if match.group(2) else end
            elif match.group(2):
                suffix = min(size, int(match.group(2)))
                start = size - suffix
            if start > end or start >= size:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            status = HTTPStatus.PARTIAL_CONTENT
        length = max(0, end - start + 1)
        self.send_response(status)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "private, max-age=3600")
        if status == HTTPStatus.PARTIAL_CONTENT:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with path.open("rb") as source:
            source.seek(start)
            remaining = length
            while remaining > 0:
                chunk = source.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def provider_key(self, provider_id: str, inline_key: str = "") -> str:
        provider = PROVIDERS[provider_id]
        environment_key = os.environ.get(str(provider["environmentVariable"]), "")
        return str(inline_key or environment_key or self.credential_store.get(provider_id) or "").strip()

    def provider_summaries(self) -> list[dict[str, Any]]:
        summaries = []
        for provider_id, provider in PROVIDERS.items():
            configured = bool(self.provider_key(provider_id))
            summaries.append(
                {
                    "id": provider_id,
                    "name": provider["name"],
                    "defaultModel": provider["defaultModel"],
                    "models": provider["models"],
                    "configured": configured,
                    "credentialStorage": "temporary" if isinstance(self.credential_store, MemoryCredentialStore) else "settings-file",
                }
            )
        return summaries

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/api/health":
            self.send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "mockMode": self.mock_ai,
                    "providers": self.provider_summaries(),
                    "projectsFolder": str(self.projects.root),
                },
            )
            return
        if path == "/api/providers":
            self.send_json(HTTPStatus.OK, {"providers": self.provider_summaries(), "mockMode": self.mock_ai})
            return
        if path == "/api/preferences":
            preferences = self.credential_store.get_preferences() if isinstance(self.credential_store, JsonCredentialStore) else {
                "copyPromptOnExport": True,
                "openFolderOnExport": True,
            }
            self.send_json(HTTPStatus.OK, {"preferences": preferences})
            return
        if path == "/api/projects":
            self.send_json(HTTPStatus.OK, {"projects": self.projects.list(), "folder": str(self.projects.root)})
            return
        media_match = re.fullmatch(r"/api/projects/([a-z0-9-]+)/media/([^/]+)", path)
        if media_match:
            self.send_project_media(media_match.group(1), media_match.group(2))
            return
        job_match = re.fullmatch(r"/api/projects/([a-z0-9-]+)/video-jobs/(video-job-[a-f0-9]+)", path)
        if job_match:
            try: self.send_json(HTTPStatus.OK, self.video_jobs.get(*job_match.groups()))
            except FileNotFoundError as error: self.send_json(HTTPStatus.NOT_FOUND, {"error": str(error)})
            return
        match = re.fullmatch(r"/api/projects/([a-z0-9-]+)", path)
        if match:
            try:
                project = self.projects.load(match.group(1))
            except FileNotFoundError as error:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": str(error)})
                return
            except (OSError, ValueError, json.JSONDecodeError) as error:
                self.send_json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(error)})
                return
            self.send_json(HTTPStatus.OK, project)
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self.read_json_body()
        if body is None:
            return
        if path == "/api/draft":
            self.handle_draft(body)
            return
        if path == "/api/projects":
            try:
                project = self.projects.create(str(body.get("name") or "Untitled project"))
            except (OSError, ValueError) as error:
                self.send_json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(error)})
                return
            self.send_json(HTTPStatus.CREATED, project)
            return
        if path == "/api/preferences":
            if isinstance(self.credential_store, JsonCredentialStore):
                try:
                    preferences = self.credential_store.set_preferences(body)
                except (OSError, ValueError) as error:
                    self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(error)})
                    return
            else:
                preferences = {
                    "copyPromptOnExport": bool(body.get("copyPromptOnExport", True)),
                    "openFolderOnExport": bool(body.get("openFolderOnExport", True)),
                }
            self.send_json(HTTPStatus.OK, {"preferences": preferences})
            return
        match = re.fullmatch(r"/api/projects/([a-z0-9-]+)/videos/import-url", path)
        if match:
            try:
                result = self.projects.import_video_url(match.group(1), str(body.get("url") or "").strip())
            except FileNotFoundError as error:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": str(error)})
                return
            except (OSError, ValueError) as error:
                self.send_json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(error)})
                return
            self.send_json(HTTPStatus.CREATED, result)
            return
        match = re.fullmatch(r"/api/projects/([a-z0-9-]+)/video-jobs", path)
        if match:
            try: result = self.video_jobs.create(match.group(1), str(body.get("url") or "").strip())
            except FileNotFoundError as error: self.send_json(HTTPStatus.NOT_FOUND, {"error": str(error)}); return
            except ValueError as error: self.send_json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(error)}); return
            self.send_json(HTTPStatus.CREATED, result)
            return
        match = re.fullmatch(r"/api/projects/([a-z0-9-]+)/export", path)
        if match:
            files = body.get("files")
            if not isinstance(files, list) or not files or len(files) > 100:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Export files are missing or invalid."})
                return
            try:
                result = self.projects.export(match.group(1), files, bool(body.get("openFolder")))
            except FileNotFoundError as error:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": str(error)})
                return
            except (OSError, ValueError, json.JSONDecodeError) as error:
                self.send_json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(error)})
                return
            self.send_json(HTTPStatus.CREATED, result)
            return
        match = re.fullmatch(r"/api/projects/([a-z0-9-]+)/duplicate", path)
        if match:
            try:
                project = self.projects.duplicate(match.group(1))
            except FileNotFoundError as error:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": str(error)})
                return
            except (OSError, ValueError, json.JSONDecodeError) as error:
                self.send_json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(error)})
                return
            self.send_json(HTTPStatus.CREATED, project)
            return
        match = re.fullmatch(r"/api/providers/([a-z0-9-]+)/credential", path)
        if match:
            self.handle_credential_save(match.group(1), body)
            return
        self.send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})

    def do_PUT(self) -> None:  # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        match = re.fullmatch(r"/api/projects/([a-z0-9-]+)", path)
        if not match:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return
        body = self.read_json_body()
        if body is None:
            return
        snapshot = body.get("snapshot")
        if not isinstance(snapshot, dict):
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "A project snapshot is required."})
            return
        try:
            project = self.projects.save(match.group(1), snapshot)
        except FileNotFoundError as error:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": str(error)})
            return
        except (OSError, ValueError, json.JSONDecodeError) as error:
            self.send_json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(error)})
            return
        self.send_json(HTTPStatus.OK, project)

    def do_PATCH(self) -> None:  # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        match = re.fullmatch(r"/api/projects/([a-z0-9-]+)", path)
        if not match:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return
        body = self.read_json_body()
        if body is None:
            return
        try:
            project = self.projects.rename(match.group(1), str(body.get("name") or ""))
        except FileNotFoundError as error:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": str(error)})
            return
        except (OSError, ValueError, json.JSONDecodeError) as error:
            self.send_json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(error)})
            return
        self.send_json(HTTPStatus.OK, project)

    def do_DELETE(self) -> None:  # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        job_match = re.fullmatch(r"/api/projects/([a-z0-9-]+)/video-jobs/(video-job-[a-f0-9]+)", path)
        if job_match:
            try: self.send_json(HTTPStatus.OK, self.video_jobs.cancel(*job_match.groups()))
            except FileNotFoundError as error: self.send_json(HTTPStatus.NOT_FOUND, {"error": str(error)})
            return
        project_match = re.fullmatch(r"/api/projects/([a-z0-9-]+)", path)
        if project_match:
            try:
                deleted_folder = self.projects.delete(project_match.group(1))
            except FileNotFoundError as error:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": str(error)})
                return
            except (OSError, ValueError) as error:
                self.send_json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(error)})
                return
            self.send_json(HTTPStatus.OK, {"ok": True, "folder": deleted_folder})
            return
        match = re.fullmatch(r"/api/providers/([a-z0-9-]+)/credential", path)
        if not match or match.group(1) not in PROVIDERS:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return
        try:
            self.credential_store.delete(match.group(1))
        except OSError as error:
            self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(error)})
            return
        self.send_json(HTTPStatus.OK, {"ok": True, "provider": match.group(1)})

    def handle_credential_save(self, provider_id: str, body: dict[str, Any]) -> None:
        if provider_id not in PROVIDERS:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "Unsupported provider."})
            return
        api_key = str(body.get("apiKey") or "").strip()
        if len(api_key) < 8:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Enter a valid API key."})
            return
        try:
            if not self.mock_ai:
                validate_provider_credential(provider_id, api_key)
            self.credential_store.set(provider_id, api_key)
        except (OSError, RuntimeError, ValueError) as error:
            self.send_json(HTTPStatus.BAD_GATEWAY, {"error": str(error)})
            return
        self.send_json(
            HTTPStatus.OK,
            {
                "ok": True,
                "provider": provider_id,
                "configured": True,
                "validated": not self.mock_ai,
                "storage": "temporary" if isinstance(self.credential_store, MemoryCredentialStore) else "settings-file",
            },
        )

    def handle_draft(self, body: dict[str, Any]) -> None:
        payload, validation_error = validate_payload(body)
        if validation_error:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": validation_error})
            return
        assert payload is not None
        provider_id = str(payload.get("provider") or "openai")
        if provider_id not in PROVIDERS:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Unsupported drafting provider."})
            return
        if self.mock_ai:
            result = mock_draft(payload)
            result["provider"] = provider_id
            self.send_json(HTTPStatus.OK, result)
            return
        api_key = self.provider_key(provider_id, str(payload.pop("apiKey", "") or ""))
        if not api_key:
            self.send_json(
                HTTPStatus.UNAUTHORIZED,
                {"error": f"Add and save a {PROVIDERS[provider_id]['name']} API key in AI settings."},
            )
            return
        try:
            result = call_openai(payload, api_key) if provider_id == "openai" else call_gemini(payload, api_key)
            result["provider"] = provider_id
        except (RuntimeError, ValueError, json.JSONDecodeError) as error:
            self.send_json(HTTPStatus.BAD_GATEWAY, {"error": str(error)})
            return
        self.send_json(HTTPStatus.OK, result)


class ExclusiveThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = False

    def server_bind(self) -> None:
        if sys.platform == "win32" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def main() -> None:
    default_settings_file = Path(
        os.environ.get("LOCALAPPDATA") or (Path.home() / ".ai-canvas")
    ) / "AI Canvas" / "settings.json"
    parser = argparse.ArgumentParser(description="Run the local AI Canvas prototype server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4173)
    parser.add_argument("--mock-ai", action="store_true", help="Return structured mock drafts without network access.")
    parser.add_argument("--volatile-credentials", action="store_true", help="Keep provider keys in memory for this run.")
    parser.add_argument(
        "--settings-file",
        type=Path,
        default=default_settings_file,
        help="App settings file used for provider keys; kept outside project folders.",
    )
    parser.add_argument(
        "--projects-dir",
        type=Path,
        default=Path.home() / "Documents" / "AI Canvas Projects",
        help="Root folder containing one directory per project.",
    )
    args = parser.parse_args()
    handler = partial(CanvasRequestHandler, directory=str(STATIC_DIR))
    server = ExclusiveThreadingHTTPServer((args.host, args.port), handler)
    server.mock_ai = args.mock_ai  # type: ignore[attr-defined]
    if args.volatile_credentials:
        server.credential_store = MemoryCredentialStore()  # type: ignore[attr-defined]
    else:
        server.credential_store = JsonCredentialStore(args.settings_file)  # type: ignore[attr-defined]
    server.project_repository = ProjectRepository(args.projects_dir)  # type: ignore[attr-defined]
    server.video_jobs = VideoJobManager(server.project_repository)  # type: ignore[attr-defined]
    mode = "mock AI" if args.mock_ai else "provider APIs"
    print(f"AI Canvas running at http://{args.host}:{args.port} ({mode})")
    print(f"Projects folder: {server.project_repository.root}")  # type: ignore[attr-defined]
    if isinstance(server.credential_store, JsonCredentialStore):  # type: ignore[attr-defined]
        print(f"Settings file: {server.credential_store.path}")  # type: ignore[attr-defined]
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
