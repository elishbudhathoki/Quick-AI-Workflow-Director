"""Credential migration and provider request shape checks."""

import json
import io
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "prototype"))
import server  # noqa: E402


class ProviderSetupTests(unittest.TestCase):
    def test_custom_endpoint_requires_https_or_loopback(self):
        self.assertEqual(server.validate_custom_api_base("http://127.0.0.1:1234/v1/"), "http://127.0.0.1:1234/v1")
        self.assertEqual(server.validate_custom_api_base("https://example.com/v1"), "https://example.com/v1")
        for address in ("http://example.com/v1", "https://user:secret@example.com/v1", "https://example.com/v1?key=secret"):
            with self.assertRaises(ValueError):
                server.validate_custom_api_base(address)

    def test_compatible_request_keeps_images_and_model(self):
        captured = {}

        def fake_open(request, timeout):
            captured["url"] = request.full_url
            captured["body"] = json.loads(request.data)
            return io.BytesIO(json.dumps({"choices": [{"message": {"content": '{"summary":"ok"}'}}]}).encode())

        payload = {"model": "qwen/qwen3.6-27b", "objective": "Test", "draftingInstructions": "", "references": [
            {"filename": "R01.png", "instruction": "Use color", "imageDataUrl": "data:image/png;base64,aGVsbG8="},
        ]}
        with patch.object(server.urllib.request, "urlopen", side_effect=fake_open):
            self.assertEqual(server.call_openai_compatible(payload, "test-key", "groq")["summary"], "ok")
        self.assertEqual(captured["url"], "https://api.groq.com/openai/v1/chat/completions")
        self.assertEqual(captured["body"]["model"], "qwen/qwen3.6-27b")
        self.assertEqual(captured["body"]["messages"][1]["content"][2]["image_url"]["url"], payload["references"][0]["imageDataUrl"])

    def test_legacy_key_moves_to_device_store_and_leaves_preferences_clean(self):
        secrets = {}
        fake = types.SimpleNamespace(
            get_password=lambda service, name: secrets.get((service, name)),
            set_password=lambda service, name, value: secrets.__setitem__((service, name), value),
            delete_password=lambda service, name: secrets.pop((service, name)),
        )
        with tempfile.TemporaryDirectory() as folder, patch.dict(sys.modules, {"keyring": fake}):
            path = Path(folder) / "settings.json"
            path.write_text(json.dumps({"providers": {"gemini": {"apiKey": "legacy-test-key"}}}), encoding="utf-8")
            store = server.JsonCredentialStore(path)
            self.assertEqual(store.get("gemini"), "legacy-test-key")
            self.assertEqual(secrets[("AI Canvas", "gemini")], "legacy-test-key")
            self.assertNotIn("legacy-test-key", path.read_text(encoding="utf-8"))
            store.set("openai", "new-test-key")
            self.assertNotIn("new-test-key", path.read_text(encoding="utf-8"))
            self.assertEqual(store.get("openai"), "new-test-key")
            store.delete("openai")
            self.assertIsNone(store.get("openai"))

    def test_missing_device_store_never_writes_plaintext_key(self):
        fake = types.SimpleNamespace(set_password=lambda *args: (_ for _ in ()).throw(RuntimeError("locked")))
        with tempfile.TemporaryDirectory() as folder, patch.dict(sys.modules, {"keyring": fake}):
            path = Path(folder) / "settings.json"
            store = server.JsonCredentialStore(path)
            with self.assertRaises(OSError):
                store.set("gemini", "test-secret")
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
