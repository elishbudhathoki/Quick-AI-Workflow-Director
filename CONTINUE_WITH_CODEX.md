# Continue AI Canvas with Codex

Use this message when opening the migrated workspace in a new Codex task:

> Continue building AI Canvas from the existing checkpoint. Read `MIGRATION_HANDOFF.md` completely, then read the relevant sections of `AI_CANVAS_MVP_SPEC.md`. Do not restart or replace the prototype. First run `migration\Verify-AICanvasEnvironment.ps1`, inspect the existing uncommitted source, and run the Python/JavaScript syntax checks documented in the handoff. Preserve the restored `AI Canvas Projects` folders and never expose `%LOCALAPPDATA%\AI Canvas\settings.json` or its API keys. Finish verification of the paused video edits, then implement the general public video-page downloader with the open-source `yt-dlp` dependency using the background-job design in the handoff. Keep the current direct-file downloader as a fast path. Detect and install missing Python, yt-dlp, and FFmpeg dependencies only after verifying what is absent. Do not build site-specific downloaders from scratch, bypass authentication/DRM/paywalls, or silently send project media to external services. Test with `--mock-ai` and a small permitted video fixture before using a real provider.

Before editing, confirm these restored locations:

- Workspace: the folder containing this file.
- Projects: `%USERPROFILE%\Documents\AI Canvas Projects`.
- Optional credentials: `%LOCALAPPDATA%\AI Canvas\settings.json`.

The authoritative detailed checkpoint is `MIGRATION_HANDOFF.md`.
