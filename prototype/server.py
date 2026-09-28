"""Local AI Canvas development server.

Serves the dependency-free prototype and provides a same-origin drafting API.
API keys are read from environment variables or the operating system credential
store. Preferences live outside project folders and are never exported.
"""

from __future__ import annotations

import argparse
import base64
import ipaddress
import io
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
import zipfile
from datetime import datetime, timezone
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


STATIC_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL = "gemini-3.6-flash"
MAX_BODY_BYTES = 320 * 1024 * 1024
MAX_VIDEO_BYTES = 240 * 1024 * 1024
MAX_IMAGE_BYTES = 24 * 1024 * 1024
MAX_REFERENCES = 30


def find_ffmpeg() -> str | None:
    configured = os.environ.get("FFMPEG_BINARY") or shutil.which("ffmpeg")
    if configured:
        return configured
    try:
        import imageio_ffmpeg  # type: ignore[import-not-found]

        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, OSError):
        return None


def default_data_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "AI Canvas"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "AI Canvas"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "ai-canvas"


def default_projects_dir() -> Path:
    configured = os.environ.get("AI_CANVAS_PROJECTS_DIR")
    if configured:
        return Path(configured).expanduser()
    documents = Path.home() / "Documents"
    if sys.platform == "win32" or documents.is_dir():
        return documents / "AI Canvas Projects"
    return default_data_dir() / "projects"


PROVIDERS: dict[str, dict[str, Any]] = {
    "gemini": {
        "id": "gemini", "name": "Google Gemini", "environmentVariable": "GEMINI_API_KEY",
        "defaultModel": "gemini-3.6-flash",
        "models": [
            {"id": "gemini-3.6-flash", "name": "Gemini 3.6 Flash", "note": "Balanced"},
            {"id": "gemini-3.1-pro-preview", "name": "Gemini 3.1 Pro Preview", "note": "Quality"},
            {"id": "gemini-3.5-flash-lite", "name": "Gemini 3.5 Flash-Lite", "note": "Economical"},
        ],
    },
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
    "groq": {
        "id": "groq", "name": "Groq", "environmentVariable": "GROQ_API_KEY",
        "defaultModel": "qwen/qwen3.6-27b",
        "models": [{"id": "qwen/qwen3.6-27b", "name": "Qwen 3.6 27B", "note": "Fast vision"}],
        "apiBase": "https://api.groq.com/openai/v1",
    },
    "openrouter": {
        "id": "openrouter", "name": "OpenRouter", "environmentVariable": "OPENROUTER_API_KEY",
        "defaultModel": "google/gemini-3.8-flash",
        "models": [
            {"id": "google/gemini-3.8-flash", "name": "Gemini 3.8 Flash", "note": "Vision"},
            {"id": "openai/gpt-5.6-luna", "name": "GPT-5.6 Luna", "note": "Vision"},
        ],
        "apiBase": "https://openrouter.ai/api/v1",
    },
    "anthropic": {
        "id": "anthropic", "name": "Anthropic Claude", "environmentVariable": "ANTHROPIC_API_KEY",
        "defaultModel": "claude-sonnet-5",
        "models": [{"id": "claude-sonnet-5", "name": "Claude Sonnet 5", "note": "Vision"}],
    },
    "xai": {
        "id": "xai", "name": "xAI Grok", "environmentVariable": "XAI_API_KEY",
        "defaultModel": "grok-4.7",
        "models": [{"id": "grok-4.7", "name": "Grok 4.7", "note": "Vision"}],
        "apiBase": "https://api.x.ai/v1",
    },
    "mistral": {
        "id": "mistral", "name": "Mistral", "environmentVariable": "MISTRAL_API_KEY",
        "defaultModel": "mistral-small-latest",
        "models": [{"id": "mistral-small-latest", "name": "Mistral Small", "note": "Vision"}],
        "apiBase": "https://api.mistral.ai/v1",
    },
    "custom": {
        "id": "custom", "name": "Custom API", "environmentVariable": "AI_CANVAS_CUSTOM_API_KEY",
        "defaultModel": "vision-model",
        "models": [{"id": "vision-model", "name": "Enter model ID below", "note": ""}],
        "apiBase": "http://127.0.0.1:1234/v1",
    },
}


def validate_custom_api_base(value: str) -> str:
    parsed = urllib.parse.urlparse(value.strip())
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Enter an API base URL without credentials, query, or fragment.")
    if parsed.scheme == "https":
        return value.rstrip("/")
    if parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
        return value.rstrip("/")
    raise ValueError("Custom API URLs must use HTTPS, or HTTP on this device only.")


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
    """JSON preferences with provider secrets held by the OS credential store."""

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
        try:
            import keyring
            secret = keyring.get_password("AI Canvas", provider_id)
            legacy = self.read().get("providers", {}).get(provider_id, {})
            if isinstance(legacy, dict) and legacy.get("apiKey"):
                if not secret:
                    secret = str(legacy["apiKey"])
                    keyring.set_password("AI Canvas", provider_id, secret)
                data = self.read()
                data["providers"].pop(provider_id, None)
                self.write(data)
            return secret or None
        except Exception as error:
            raise OSError(f"Device credential store unavailable: {error}") from error

    def set(self, provider_id: str, secret: str) -> None:
        try:
            import keyring
            keyring.set_password("AI Canvas", provider_id, secret)
            data = self.read()
            data.setdefault("providers", {}).pop(provider_id, None)
            self.write(data)
        except Exception as error:
            raise OSError(f"Could not save key in the device credential store: {error}") from error

    def delete(self, provider_id: str) -> None:
        try:
            import keyring
            if keyring.get_password("AI Canvas", provider_id):
                keyring.delete_password("AI Canvas", provider_id)
            data = self.read()
            data.setdefault("providers", {}).pop(provider_id, None)
            self.write(data)
        except Exception as error:
            raise OSError(f"Could not remove key from the device credential store: {error}") from error

    def get_preferences(self) -> dict[str, Any]:
        preferences = self.read().get("preferences", {})
        return {
            "copyPromptOnExport": bool(preferences.get("copyPromptOnExport", True)),
            "openFolderOnExport": bool(preferences.get("openFolderOnExport", True)),
            "highestQualityMedia": True,
            "lastActiveProjectId": str(preferences.get("lastActiveProjectId") or "") or None,
            "providerId": str(preferences.get("providerId") or "gemini"),
            "customApiBase": str(preferences.get("customApiBase") or PROVIDERS["custom"]["apiBase"]),
            "openProjectIds": [str(value) for value in preferences.get("openProjectIds", []) if isinstance(value, str)],
        }

    def set_preferences(self, preferences: dict[str, Any]) -> dict[str, Any]:
        data = self.read()
        current = data.setdefault("preferences", {})
        for key in ("copyPromptOnExport", "openFolderOnExport", "highestQualityMedia"):
            if key in preferences:
                current[key] = bool(preferences[key])
        if "lastActiveProjectId" in preferences:
            value = preferences.get("lastActiveProjectId")
            current["lastActiveProjectId"] = str(value) if value else None
        if "providerId" in preferences:
            provider_id = str(preferences["providerId"])
            if provider_id not in PROVIDERS:
                raise ValueError("Unsupported provider.")
            current["providerId"] = provider_id
        if "customApiBase" in preferences:
            current["customApiBase"] = validate_custom_api_base(str(preferences["customApiBase"]))
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

    def save(self, project_id: str, snapshot: dict[str, Any], snapshot_revision: int | None = None) -> dict[str, Any]:
        folder = self.folder(project_id)
        record_file = folder / "project.json"
        if not record_file.exists():
            raise FileNotFoundError("Project not found.")
        record = json.loads(record_file.read_text(encoding="utf-8"))
        saved_revision = int(record.get("snapshotRevision") or 0)
        if snapshot_revision is not None and snapshot_revision < saved_revision:
            return self.summary(record, folder)
        stored_snapshot = json.loads(json.dumps(snapshot))
        media_folder = folder / "media"
        media_folder.mkdir(exist_ok=True)
        for asset in stored_snapshot.get("assets") or []:
            asset.pop("scrubProxySrc", None)
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
        if snapshot_revision is not None:
            record["snapshotRevision"] = snapshot_revision
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
            raise ValueError("Paste a valid http or https URL.")
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port or 443)}
        except socket.gaierror as error:
            raise ValueError(f"Link host could not be resolved: {error}") from error
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                raise ValueError("Local or private-network URLs are not allowed.")
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

    def import_image_url(self, project_id: str, url: str) -> dict[str, Any]:
        from PIL import Image, UnidentifiedImageError

        folder = self.folder(project_id)
        parsed = self.validate_public_url(url)
        request = urllib.request.Request(url, headers={"User-Agent": "AI Canvas/0.4"})

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, request, fp, code, msg, headers, newurl):
                raise ValueError("Use the direct public image URL, without a redirect.")

        try:
            with urllib.request.build_opener(NoRedirect()).open(request, timeout=45) as response:
                if int(response.headers.get("Content-Length") or 0) > MAX_IMAGE_BYTES:
                    raise ValueError("Image exceeds the 24 MB import limit.")
                data = response.read(MAX_IMAGE_BYTES + 1)
        except urllib.error.HTTPError as error:
            raise ValueError(f"Image download failed ({error.code}).") from error
        except urllib.error.URLError as error:
            raise ValueError(f"Image download failed: {error.reason}") from error
        if len(data) > MAX_IMAGE_BYTES:
            raise ValueError("Image exceeds the 24 MB import limit.")
        try:
            with Image.open(io.BytesIO(data)) as image:
                image.load()
                if image.width * image.height > 32_000_000:
                    raise ValueError("Image exceeds the 32 megapixel limit.")
                extension = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}.get(image.format)
                if not extension:
                    raise ValueError("Use a direct PNG, JPEG, or WebP image URL.")
                width, height = image.size
        except (OSError, UnidentifiedImageError) as error:
            raise ValueError("The URL did not return a readable image.") from error
        raw_name = Path(urllib.parse.unquote(parsed.path)).stem or "Downloaded image"
        display_name = self.clean_name(raw_name) + extension
        safe_stem = re.sub(r"[^a-zA-Z0-9_-]", "-", raw_name).strip("-")[:42] or "image"
        filename = f"image-{safe_stem}-{secrets.token_hex(4)}{extension}"
        relative = f"media/{filename}"
        (folder / relative).write_bytes(data)
        return {"name": display_name, "sourceFile": relative,
                "src": f"/api/projects/{project_id}/media/{urllib.parse.quote(filename)}",
                "width": width, "height": height, "size": len(data)}

    def media_file(self, project_id: str, filename: str) -> Path:
        folder = self.folder(project_id)
        media_folder = (folder / "media").resolve()
        path = (media_folder / filename).resolve()
        if media_folder not in path.parents or path.parent != media_folder:
            raise ValueError("Invalid media filename.")
        if not path.exists() or not path.is_file():
            raise FileNotFoundError("Project media file not found.")
        return path

    def create_scrub_proxy(self, project_id: str, source_file: str) -> dict[str, Any]:
        folder = self.folder(project_id)
        source = (folder / str(source_file)).resolve()
        media_folder = (folder / "media").resolve()
        if media_folder not in source.parents or source.parent != media_folder:
            raise ValueError("Invalid video source path.")
        if not source.exists() or not source.is_file():
            raise FileNotFoundError("Source video was not found.")
        proxy = media_folder / f"{source.stem}.scrub.mp4"
        if proxy.exists() and proxy.stat().st_size > 0 and proxy.stat().st_mtime >= source.stat().st_mtime:
            return {
                "sourceFile": f"media/{proxy.name}",
                "src": f"/api/projects/{project_id}/media/{urllib.parse.quote(proxy.name)}",
                "cached": True,
            }
        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            raise RuntimeError("FFmpeg is required to create the fast local scrub proxy.")
        temporary = media_folder / f".{proxy.name}.{secrets.token_hex(4)}.tmp.mp4"
        command = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
            "-map", "0:v:0", "-an",
            "-vf", "scale=960:960:force_original_aspect_ratio=decrease:force_divisible_by=2",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
            "-g", "12", "-keyint_min", "12", "-sc_threshold", "0",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(temporary),
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=600, check=False)
            if result.returncode != 0 or not temporary.exists() or temporary.stat().st_size == 0:
                detail = (result.stderr or result.stdout or "FFmpeg could not create the proxy.").strip()
                raise RuntimeError(detail[-800:])
            temporary.replace(proxy)
        finally:
            temporary.unlink(missing_ok=True)
        return {
            "sourceFile": f"media/{proxy.name}",
            "src": f"/api/projects/{project_id}/media/{urllib.parse.quote(proxy.name)}",
            "cached": False,
        }

    def video_metadata(self, project_id: str, source_file: str) -> dict[str, Any]:
        folder = self.folder(project_id)
        source = (folder / str(source_file)).resolve()
        media_folder = (folder / "media").resolve()
        if source.parent != media_folder:
            raise ValueError("Invalid video source path.")
        if not source.is_file():
            raise FileNotFoundError("Source video was not found.")
        try:
            import cv2
        except ImportError:
            return {"frameRate": None, "frameCount": None}
        capture = cv2.VideoCapture(str(source))
        try:
            fps = float(capture.get(cv2.CAP_PROP_FPS)) if capture.isOpened() else 0
            count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) if capture.isOpened() else 0
        finally:
            capture.release()
        return {
            "frameRate": round(fps, 3) if 1 <= fps <= 240 else None,
            "frameCount": count if count > 0 else None,
        }

    def export_maps(self, project_id: str, source_name: str, source_asset_id: str, maps: list[dict[str, Any]]) -> str:
        folder = self.folder(project_id)
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output = folder / "exports" / f"maps_{stamp}"
        suffix = 2
        while output.exists():
            output = folder / "exports" / f"maps_{stamp}_{suffix}"
            suffix += 1
        output.mkdir(parents=True)
        stem = re.sub(r"[^a-zA-Z0-9_-]+", "-", Path(source_name).stem).strip("-")[:48] or "reference"
        records = []
        for item in maps:
            kind = item["type"]
            filename = f"{stem}_{kind}.png"
            _, data = self.parse_data_url(item["dataUrl"])
            (output / filename).write_bytes(data)
            record = {"type": kind, "filename": filename, "width": item["width"], "height": item["height"],
                      "engine": item.get("engine", "built-in"), "workflowName": item.get("workflowName")}
            if item.get("rawDataUrl"):
                raw_name = f"{stem}_{kind}_raw16.png"
                _, raw_data = self.parse_data_url(item["rawDataUrl"])
                (output / raw_name).write_bytes(raw_data)
                record["rawFilename"] = raw_name
            records.append(record)
        (output / "manifest.json").write_text(json.dumps({
            "schemaVersion": 1, "sourceAssetId": source_asset_id, "sourceName": source_name,
            "createdAt": utc_now(), "maps": records,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(output)

    def map_workflow(self, project_id: str, kind: str) -> dict[str, Any]:
        if kind not in {"canny", "lineart", "depth", "pose", "softedge", "normal", "scribble", "animal_pose"}:
            raise ValueError("Unsupported map type.")
        path = self.folder(project_id) / "map_workflows" / f"{kind}.json"
        if not path.is_file():
            raise FileNotFoundError(f"Add a ComfyUI workflow for {kind} first.")
        return json.loads(path.read_text(encoding="utf-8"))

    def list_map_workflows(self, project_id: str) -> dict[str, Any]:
        self.folder(project_id)
        result = {}
        for kind in ("canny", "lineart", "depth", "pose", "softedge", "normal", "scribble", "animal_pose"):
            try:
                saved = self.map_workflow(project_id, kind)
                result[kind] = {"name": saved.get("name"), "serverUrl": saved.get("serverUrl"),
                                "inputNodeId": saved.get("inputNodeId"), "outputNodeId": saved.get("outputNodeId")}
            except FileNotFoundError:
                pass
        return result

    def list_map_exports(self, project_id: str) -> list[dict[str, Any]]:
        exports = self.folder(project_id) / "exports"
        batches = []
        for folder in exports.glob("maps_*"):
            if not folder.is_dir() or not re.fullmatch(r"maps_[0-9_-]+", folder.name):
                continue
            try:
                manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            batches.append({
                "name": folder.name,
                "sourceAssetId": manifest.get("sourceAssetId"),
                "createdAt": manifest.get("createdAt"),
                "mapCount": len(manifest.get("maps") or []),
                "downloadUrl": f"/api/projects/{project_id}/maps/{folder.name}.zip",
            })
        return sorted(batches, key=lambda batch: batch["name"], reverse=True)

    def save_map_workflow(self, project_id: str, config: dict[str, Any]) -> dict[str, Any]:
        from comfy_maps import MAP_TYPES, server_url, validate_workflow

        kind = str(config.get("type") or "")
        if kind not in MAP_TYPES:
            raise ValueError("Choose a supported map type.")
        normalized = {
            "type": kind,
            "name": str(config.get("name") or f"{kind} workflow")[:120],
            "serverUrl": server_url(str(config.get("serverUrl") or "")),
            "inputNodeId": str(config.get("inputNodeId") or ""),
            "outputNodeId": str(config.get("outputNodeId") or ""),
            "workflow": validate_workflow(config.get("workflow"), str(config.get("inputNodeId") or ""),
                                          str(config.get("outputNodeId") or "")),
        }
        folder = self.folder(project_id) / "map_workflows"
        folder.mkdir(exist_ok=True)
        path = folder / f"{kind}.json"
        temporary = path.with_suffix(".json.tmp")
        try:
            temporary.write_text(json.dumps(normalized, ensure_ascii=False), encoding="utf-8")
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
        return {key: normalized[key] for key in ("type", "name", "serverUrl", "inputNodeId", "outputNodeId")}

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
                    proxy = source_file.parent / f"{source_file.stem}.scrub.mp4"
                    if proxy.exists() and proxy.stat().st_size > 0:
                        asset["scrubProxySrc"] = f"/api/projects/{project_id}/media/{urllib.parse.quote(proxy.name)}"
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


def call_openai_compatible(payload: dict[str, Any], api_key: str, provider_id: str, api_base: str | None = None) -> dict[str, Any]:
    provider = PROVIDERS[provider_id]
    content: list[dict[str, Any]] = [{
        "type": "text",
        "text": (
            f"CREATIVE OBJECTIVE\n{str(payload.get('objective') or '[No objective supplied]')}\n\n"
            f"DRAFTING FORMAT INSTRUCTIONS\n{str(payload.get('draftingInstructions') or '[Use a clear production-ready structure]')}\n\n"
            "REFERENCE CROPS\nEach metadata block is followed by its matching image crop. Return JSON only."
        ),
    }]
    for reference in payload["references"]:
        content.extend((
            {"type": "text", "text": f"Filename: {reference['filename']}\nUser instruction: {reference['instruction']}"},
            {"type": "image_url", "image_url": {"url": reference["imageDataUrl"]}},
        ))
    request = urllib.request.Request(
        str(api_base or provider["apiBase"]) + "/chat/completions",
        data=json_bytes({
            "model": str(payload.get("model") or provider["defaultModel"]),
            "messages": [
                {"role": "system", "content": SYSTEM_INSTRUCTIONS + "\nReturn a JSON object matching this schema: " + json.dumps(OUTPUT_SCHEMA)},
                {"role": "user", "content": content},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": 6000,
        }),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
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
        raise provider_network_error(str(provider["name"]), error) from error
    output = raw["choices"][0]["message"]["content"]
    if isinstance(output, list):
        output = "".join(str(part.get("text") or "") for part in output if isinstance(part, dict))
    parsed = json.loads(str(output))
    parsed["model"] = raw.get("model") or payload.get("model") or provider["defaultModel"]
    parsed["responseId"] = raw.get("id")
    parsed["usage"] = raw.get("usage")
    return parsed


def call_anthropic(payload: dict[str, Any], api_key: str) -> dict[str, Any]:
    content: list[dict[str, Any]] = [{
        "type": "text",
        "text": (
            f"CREATIVE OBJECTIVE\n{str(payload.get('objective') or '[No objective supplied]')}\n\n"
            f"DRAFTING FORMAT INSTRUCTIONS\n{str(payload.get('draftingInstructions') or '[Use a clear production-ready structure]')}\n\n"
            "REFERENCE CROPS\nEach metadata block is followed by its matching image crop. "
            "Return only JSON matching this schema: " + json.dumps(OUTPUT_SCHEMA)
        ),
    }]
    for reference in payload["references"]:
        mime_type, encoded = ProjectRepository.parse_data_url(str(reference["imageDataUrl"]))
        content.extend((
            {"type": "text", "text": f"Filename: {reference['filename']}\nUser instruction: {reference['instruction']}"},
            {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": base64.b64encode(encoded).decode("ascii")}},
        ))
    request = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json_bytes({"model": str(payload.get("model") or PROVIDERS["anthropic"]["defaultModel"]),
                         "max_tokens": 6000, "system": SYSTEM_INSTRUCTIONS,
                         "messages": [{"role": "user", "content": content}]}),
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
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
        raise provider_network_error("Anthropic Claude", error) from error
    output = "".join(part.get("text", "") for part in raw.get("content", []) if part.get("type") == "text")
    parsed = json.loads(output)
    parsed["model"] = raw.get("model") or payload.get("model") or PROVIDERS["anthropic"]["defaultModel"]
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


def validate_provider_credential(provider_id: str, api_key: str, api_base: str | None = None) -> None:
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
    elif provider_id == "anthropic":
        request = urllib.request.Request(
            "https://api.anthropic.com/v1/models",
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
        )
    elif provider_id in {"groq", "openrouter", "xai", "mistral", "custom"}:
        request = urllib.request.Request(
            str(api_base or PROVIDERS[provider_id]["apiBase"]) + "/models",
            headers={"Authorization": f"Bearer {api_key}"},
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
        self.restore_unfinished()

    def persist_project(self, project_id: str) -> None:
        folder = self.projects.folder(project_id)
        records = [job for job in self.jobs.values() if job["projectId"] == project_id]
        temporary = folder / "video-jobs.json.tmp"
        temporary.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(folder / "video-jobs.json")

    def restore_unfinished(self) -> None:
        for path in self.projects.root.glob("*/video-jobs.json"):
            try:
                records = json.loads(path.read_text(encoding="utf-8"))
                for job in records if isinstance(records, list) else []:
                    if not isinstance(job, dict) or not job.get("id") or not job.get("projectId"):
                        continue
                    if job.get("state") in {"resolving", "downloading", "processing", "queued"}:
                        job.update(state="queued", error="Resuming after server restart.", updatedAt=utc_now())
                    self.jobs[str(job["id"])] = job
            except (OSError, json.JSONDecodeError):
                continue
        for job in list(self.jobs.values()):
            if job.get("state") == "queued":
                self.persist_project(str(job["projectId"]))
                threading.Thread(target=self.run, args=(str(job["id"]),), daemon=True).start()

    def create(self, project_id: str, url: str, highest_quality: bool = False) -> dict[str, Any]:
        self.projects.folder(project_id)
        self.projects.validate_public_url(url)
        job = {"id": f"video-job-{secrets.token_hex(6)}", "projectId": project_id, "url": url, "highestQuality": highest_quality,
               "state": "resolving", "progress": 0, "createdAt": utc_now(), "updatedAt": utc_now(), "error": None}
        with self.lock:
            self.jobs[job["id"]] = job
            self.persist_project(project_id)
        threading.Thread(target=self.run, args=(job["id"],), daemon=True).start()
        return dict(job)

    def list(self, project_id: str) -> list[dict[str, Any]]:
        self.projects.folder(project_id)
        with self.lock:
            return [dict(job) for job in self.jobs.values() if job["projectId"] == project_id]

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
            self.persist_project(project_id)
            return dict(self.jobs[job_id])

    def retry(self, project_id: str, job_id: str) -> dict[str, Any]:
        with self.lock:
            previous = self.jobs.get(job_id)
            if not previous or previous["projectId"] != project_id:
                raise FileNotFoundError("Video job not found.")
            if previous["state"] not in {"failed", "cancelled"}:
                raise ValueError("Only failed or cancelled video downloads can be retried.")
            url = str(previous["url"])
        return self.create(project_id, url, bool(previous.get("highestQuality")))

    def run(self, job_id: str) -> None:
        try:
            import yt_dlp
            with self.lock:
                job = self.jobs[job_id]
                url, project_id = job["url"], job["projectId"]
                job.update(state="downloading", progress=1, updatedAt=utc_now())
                self.persist_project(project_id)
            folder = self.projects.folder(project_id)
            temporary = folder / "media" / ".downloads"
            temporary.mkdir(exist_ok=True)
            # Let each extractor choose its best public format. Filtering on a
            # reported filesize rejects Pinterest streams that omit that field;
            # the post-download size check below remains the hard safety limit.
            def update_progress(data: dict[str, Any]) -> None:
                if data.get("status") != "downloading":
                    return
                with self.lock:
                    active = self.jobs.get(job_id)
                    if not active or active["state"] == "cancelled":
                        raise yt_dlp.utils.DownloadError("Download cancelled by user.")
                    total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
                    downloaded = data.get("downloaded_bytes") or 0
                    progress = min(99, max(1, round(downloaded * 100 / total))) if total else active.get("progress", 1)
                    active.update(state="downloading", progress=progress, speed=data.get("speed"), updatedAt=utc_now())

            options = {"outtmpl": str(temporary / "%(id)s.%(ext)s"), "noplaylist": True,
                       "max_filesize": MAX_VIDEO_BYTES, "quiet": True, "no_warnings": True,
                       "progress_hooks": [update_progress]}
            if job.get("highestQuality"):
                options["format"] = "bestvideo*+bestaudio/best"
            node = shutil.which("node")
            if node:
                # YouTube increasingly requires its player JavaScript to be
                # interpreted. Enable the user's installed Node runtime rather
                # than attempting to imitate a logged-in browser session.
                options["js_runtimes"] = {"node": {"path": node}}
            # Do not force YouTube's Android client: it can expose only a
            # 360p Shorts rendition. yt-dlp's default public client set can
            # choose among all anonymously available formats; high-quality
            # jobs explicitly select best video plus best audio above.
            with yt_dlp.YoutubeDL(options) as downloader:
                info = downloader.extract_info(url, download=True)
            with self.lock:
                if self.jobs[job_id]["state"] == "cancelled":
                    return
                self.jobs[job_id].update(state="processing", progress=99, updatedAt=utc_now())
                self.persist_project(project_id)
            filename = Path(downloader.prepare_filename(info))
            if not filename.exists(): raise RuntimeError("Downloader did not produce a local video file.")
            if filename.stat().st_size > MAX_VIDEO_BYTES: raise RuntimeError("Video exceeded the 240 MB local import limit.")
            target_name = f"video-{secrets.token_hex(8)}{filename.suffix.lower() or '.mp4'}"
            target = folder / "media" / target_name
            filename.replace(target)
            result = {"name": self.projects.clean_name(str(info.get("title") or "Downloaded video")) + target.suffix,
                      "mimeType": mimetypes.guess_type(target.name)[0] or "video/mp4", "sourceFile": f"media/{target_name}",
                      "src": f"/api/projects/{project_id}/media/{urllib.parse.quote(target_name)}", "size": target.stat().st_size,
                      "title": info.get("title"), "duration": info.get("duration"), "extractor": info.get("extractor"),
                      "width": info.get("width"), "height": info.get("height"),
                      "sourceUrl": url, "retrievedAt": utc_now()}
            with self.lock:
                self.jobs[job_id].update(state="ready", progress=100, result=result, updatedAt=utc_now())
                self.persist_project(project_id)
        except Exception as error:
            with self.lock:
                if self.jobs.get(job_id, {}).get("state") == "cancelled":
                    return
            message = str(error)
            if "ffmpeg is not installed" in message.lower():
                message = "FFmpeg is required to merge this source's audio and video streams. Install FFmpeg, restart AI Canvas, and retry."
            elif "drm" in message.lower():
                message = "This source is DRM-protected and cannot be downloaded."
            elif "not available" in message.lower():
                message = "This video is not publicly available to the downloader. Try another public source."
            with self.lock:
                self.jobs[job_id].update(state="failed", error=message, updatedAt=utc_now())
                self.persist_project(str(self.jobs[job_id]["projectId"]))


class CanvasRequestHandler(SimpleHTTPRequestHandler):
    server_version = "AICanvasLocal/0.3"

    def allow_local_request(self) -> bool:
        """Reject DNS rebinding and cross-site writes to the local project API."""
        host = self.headers.get("Host", "")
        try:
            parsed_host = urllib.parse.urlsplit(f"http://{host}")
            valid_host = parsed_host.hostname in {"127.0.0.1", "localhost", "::1"}
            valid_port = parsed_host.port == self.server.server_port
            valid_syntax = not parsed_host.username and not parsed_host.password and not parsed_host.path and not parsed_host.query and not parsed_host.fragment
        except ValueError:
            valid_host = valid_port = valid_syntax = False
        origin = self.headers.get("Origin")
        valid_origin = True
        if origin:
            try:
                parsed_origin = urllib.parse.urlsplit(origin)
                valid_origin = (
                    parsed_origin.scheme == "http"
                    and parsed_origin.hostname in {"127.0.0.1", "localhost", "::1"}
                    and parsed_origin.port == self.server.server_port
                    and not parsed_origin.username and not parsed_origin.password
                    and not parsed_origin.path and not parsed_origin.query and not parsed_origin.fragment
                )
            except ValueError:
                valid_origin = False
        if valid_host and valid_port and valid_syntax and valid_origin:
            return True
        self.send_json(HTTPStatus.FORBIDDEN, {"error": "AI Canvas only accepts requests from its local page."})
        return False

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
        try:
            saved_key = self.credential_store.get(provider_id)
        except OSError:
            saved_key = None
        return str(inline_key or environment_key or saved_key or "").strip()

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
                    "credentialStorage": "temporary" if isinstance(self.credential_store, MemoryCredentialStore) else "device-keychain",
                }
            )
        return summaries

    def do_GET(self) -> None:  # noqa: N802
        if not self.allow_local_request():
            return
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
                "highestQualityMedia": True,
            }
            self.send_json(HTTPStatus.OK, {"preferences": preferences})
            return
        if path == "/api/projects":
            self.send_json(HTTPStatus.OK, {"projects": self.projects.list(), "folder": str(self.projects.root)})
            return
        workflow_match = re.fullmatch(r"/api/projects/([a-z0-9-]+)/map-workflows", path)
        if workflow_match:
            try: self.send_json(HTTPStatus.OK, {"workflows": self.projects.list_map_workflows(workflow_match.group(1))})
            except FileNotFoundError as error: self.send_json(HTTPStatus.NOT_FOUND, {"error": str(error)})
            return
        map_list_match = re.fullmatch(r"/api/projects/([a-z0-9-]+)/maps", path)
        if map_list_match:
            try: self.send_json(HTTPStatus.OK, {"exports": self.projects.list_map_exports(map_list_match.group(1))})
            except FileNotFoundError as error: self.send_json(HTTPStatus.NOT_FOUND, {"error": str(error)})
            return
        maps_zip_match = re.fullmatch(r"/api/projects/([a-z0-9-]+)/maps/(maps_[0-9_-]+)\.zip", path)
        if maps_zip_match:
            try:
                project_id, batch_name = maps_zip_match.groups()
                export_folder = self.projects.folder(project_id) / "exports" / batch_name
                if not export_folder.is_dir():
                    raise FileNotFoundError("Map export not found.")
                archive = io.BytesIO()
                with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zip_output:
                    for file in export_folder.iterdir():
                        if file.is_file() and (file.suffix.lower() == ".png" or file.name == "manifest.json"):
                            zip_output.write(file, file.name)
                payload = archive.getvalue()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Disposition", f'attachment; filename="{batch_name}.zip"')
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Cache-Control", "private, no-store")
                self.end_headers()
                self.wfile.write(payload)
            except FileNotFoundError as error:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": str(error)})
            return
        media_match = re.fullmatch(r"/api/projects/([a-z0-9-]+)/media/([^/]+)", path)
        if media_match:
            self.send_project_media(media_match.group(1), media_match.group(2))
            return
        jobs_match = re.fullmatch(r"/api/projects/([a-z0-9-]+)/video-jobs", path)
        if jobs_match:
            try: self.send_json(HTTPStatus.OK, {"jobs": self.video_jobs.list(jobs_match.group(1))})
            except FileNotFoundError as error: self.send_json(HTTPStatus.NOT_FOUND, {"error": str(error)})
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
        if not self.allow_local_request():
            return
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
                    "highestQualityMedia": bool(body.get("highestQualityMedia", True)),
                }
            self.send_json(HTTPStatus.OK, {"preferences": preferences})
            return
        match = re.fullmatch(r"/api/projects/([a-z0-9-]+)/images/import-url", path)
        if match:
            try:
                result = self.projects.import_image_url(match.group(1), str(body.get("url") or "").strip())
            except FileNotFoundError as error:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": str(error)})
                return
            except (OSError, ValueError) as error:
                self.send_json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(error)})
                return
            self.send_json(HTTPStatus.CREATED, result)
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
        match = re.fullmatch(r"/api/projects/([a-z0-9-]+)/maps", path)
        if match:
            try:
                self.projects.folder(match.group(1))
                encoded = str(body.get("imageBase64") or "")
                if len(encoded) > 34 * 1024 * 1024:
                    raise ValueError("Image is too large for map generation.")
                source_bytes = base64.b64decode(encoded, validate=True)
                requested = body.get("types")
                if not isinstance(requested, list):
                    raise ValueError("Choose at least one map type.")
                if body.get("engine") == "comfyui":
                    from comfy_maps import MAP_TYPES, generate_map

                    if not requested or any(kind not in MAP_TYPES for kind in requested):
                        raise ValueError("Choose one or more supported map types.")
                    result = {"maps": [], "errors": {}, "fallbacks": []}
                    for kind in dict.fromkeys(requested):
                        try:
                            config = self.projects.map_workflow(match.group(1), kind)
                        except FileNotFoundError:
                            if kind == "animal_pose":
                                result["errors"][kind] = "Add a ComfyUI AnimalPosePreprocessor workflow for Animal pose first."
                                continue
                            from map_processor import generate_maps

                            fallback = generate_maps(source_bytes, [kind])
                            result["maps"].extend(fallback["maps"])
                            result["errors"].update(fallback["errors"])
                            result["fallbacks"].append(kind)
                            continue
                        try:
                            result["maps"].append(generate_map(source_bytes, config))
                        except Exception as error:
                            result["errors"][kind] = str(error)[:400] or "ComfyUI map generation failed."
                else:
                    from map_processor import generate_maps

                    result = generate_maps(source_bytes, requested)
                if result["maps"]:
                    result["exportFolder"] = self.projects.export_maps(
                        match.group(1), str(body.get("sourceName") or "reference"),
                        str(body.get("sourceAssetId") or ""), result["maps"]
                    )
                    result["downloadUrl"] = (f"/api/projects/{match.group(1)}/maps/"
                                             f"{Path(result['exportFolder']).name}.zip")
                    for map_item in result["maps"]:
                        map_item.pop("rawDataUrl", None)
            except FileNotFoundError as error:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": str(error)})
                return
            except (OSError, RuntimeError, ValueError, base64.binascii.Error) as error:
                self.send_json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(error)})
                return
            self.send_json(HTTPStatus.OK, result)
            return
        match = re.fullmatch(r"/api/projects/([a-z0-9-]+)/map-workflows", path)
        if match:
            try:
                saved = self.projects.save_map_workflow(match.group(1), body)
            except FileNotFoundError as error:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": str(error)})
                return
            except (OSError, ValueError) as error:
                self.send_json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(error)})
                return
            self.send_json(HTTPStatus.OK, {"workflow": saved})
            return
        match = re.fullmatch(r"/api/projects/([a-z0-9-]+)/videos/scrub-proxy", path)
        if match:
            try:
                result = self.projects.create_scrub_proxy(match.group(1), str(body.get("sourceFile") or ""))
            except FileNotFoundError as error:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": str(error)})
                return
            except (OSError, RuntimeError, ValueError) as error:
                self.send_json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(error)})
                return
            self.send_json(HTTPStatus.CREATED, result)
            return
        match = re.fullmatch(r"/api/projects/([a-z0-9-]+)/videos/metadata", path)
        if match:
            try:
                result = self.projects.video_metadata(match.group(1), str(body.get("sourceFile") or ""))
            except FileNotFoundError as error:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": str(error)})
                return
            except (OSError, ValueError) as error:
                self.send_json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(error)})
                return
            self.send_json(HTTPStatus.OK, result)
            return
        match = re.fullmatch(r"/api/projects/([a-z0-9-]+)/video-jobs", path)
        if match:
            try: result = self.video_jobs.create(match.group(1), str(body.get("url") or "").strip(), bool(body.get("highestQuality", False)))
            except FileNotFoundError as error: self.send_json(HTTPStatus.NOT_FOUND, {"error": str(error)}); return
            except ValueError as error: self.send_json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(error)}); return
            self.send_json(HTTPStatus.CREATED, result)
            return
        match = re.fullmatch(r"/api/projects/([a-z0-9-]+)/video-jobs/(video-job-[a-f0-9]+)/retry", path)
        if match:
            try: result = self.video_jobs.retry(*match.groups())
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
        if not self.allow_local_request():
            return
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
        snapshot_revision = body.get("snapshotRevision")
        if snapshot_revision is not None and (not isinstance(snapshot_revision, int) or isinstance(snapshot_revision, bool) or snapshot_revision < 0):
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Project snapshot revision is invalid."})
            return
        try:
            project = self.projects.save(match.group(1), snapshot, snapshot_revision)
        except FileNotFoundError as error:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": str(error)})
            return
        except (OSError, ValueError, json.JSONDecodeError) as error:
            self.send_json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(error)})
            return
        self.send_json(HTTPStatus.OK, project)

    def do_PATCH(self) -> None:  # noqa: N802
        if not self.allow_local_request():
            return
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
        if not self.allow_local_request():
            return
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
            custom_base = None
            if provider_id == "custom":
                custom_base = validate_custom_api_base(str(body.get("apiBase") or PROVIDERS["custom"]["apiBase"]))
            if not self.mock_ai:
                validate_provider_credential(provider_id, api_key, custom_base)
            self.credential_store.set(provider_id, api_key)
            if custom_base and isinstance(self.credential_store, JsonCredentialStore):
                self.credential_store.set_preferences({"customApiBase": custom_base})
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
                "storage": "temporary" if isinstance(self.credential_store, MemoryCredentialStore) else "device-keychain",
            },
        )

    def handle_draft(self, body: dict[str, Any]) -> None:
        payload, validation_error = validate_payload(body)
        if validation_error:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": validation_error})
            return
        assert payload is not None
        provider_id = str(payload.get("provider") or "gemini")
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
            custom_base = None
            if provider_id == "custom" and isinstance(self.credential_store, JsonCredentialStore):
                custom_base = validate_custom_api_base(self.credential_store.get_preferences()["customApiBase"])
            result = (call_openai(payload, api_key) if provider_id == "openai"
                      else call_gemini(payload, api_key) if provider_id == "gemini"
                      else call_anthropic(payload, api_key) if provider_id == "anthropic"
                      else call_openai_compatible(payload, api_key, provider_id, custom_base))
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
    default_settings_file = default_data_dir() / "settings.json"
    parser = argparse.ArgumentParser(description="Run the local AI Canvas prototype server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4173)
    parser.add_argument("--mock-ai", action="store_true", help="Return structured mock drafts without network access.")
    parser.add_argument("--volatile-credentials", action="store_true", help="Keep provider keys in memory for this run.")
    parser.add_argument(
        "--settings-file",
        type=Path,
        default=default_settings_file,
        help="App preferences file; provider keys use the device credential store.",
    )
    parser.add_argument(
        "--projects-dir",
        type=Path,
        default=default_projects_dir(),
        help="Root folder containing one directory per project.",
    )
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        parser.error("The desktop source server only binds to loopback. Use 127.0.0.1 or localhost.")
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
