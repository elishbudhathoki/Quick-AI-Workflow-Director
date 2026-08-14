# AI Canvas migration and development handoff

Updated: 2026-08-14

This document is the starting point when moving AI Canvas to another Windows computer or opening the project in a new Codex task.

## What must be moved

AI Canvas currently has three separate data locations:

1. **Source workspace** — this folder, containing `prototype/`, the product specification, and this handoff.
2. **Project data** — `%USERPROFILE%\Documents\AI Canvas Projects`. Each named project has `project.json`, `media/`, and `exports/`.
3. **App settings and API keys** — `%LOCALAPPDATA%\AI Canvas\settings.json`.

The migration bundle created by `migration\Export-AICanvasMigration.ps1` includes the source workspace and project data. It excludes app settings by default because the settings file contains provider API keys in readable form.

Current project data on the source laptop:

- `Cat` — 2 files, approximately 0.55 MB when last inventoried.
- `Human` — 17 files, approximately 3.10 MB when last inventoried.

These counts are only a checkpoint; the export script always copies the current contents.

## New laptop prerequisites

Runtime requirements for the current prototype:

- Windows 10 or 11.
- Python 3.11 or newer. The current machine was tested with Python 3.12.13.
- A modern Chromium-based browser.
- Internet access only when validating provider credentials, calling an AI provider, or downloading public videos.

Node.js is not required to run the app. It is useful for `node --check prototype\app.js`; the current machine used Node 24.19.0.

On the source laptop, Python and Node were supplied by Codex's bundled workspace runtime rather than a normal system installation. The verification script checks both PATH and the local Codex runtime cache. On a new laptop, a normal Python installation is preferable so the project also runs outside Codex.

Phase 2 downloader requirements that are **planned but not yet integrated**:

- `yt-dlp`, declared in `requirements-phase2.txt`.
- FFmpeg/FFprobe for sites or formats that require merging, remuxing, metadata inspection, proxy generation, or robust frame extraction.

On the new laptop, Codex should first inspect the environment and install only what is missing. Recommended checks:

```powershell
py -3 --version
py -3 -m pip --version
node --version
ffmpeg -version
py -3 -m pip show yt-dlp
```

For the current image workflow, only Python is mandatory. Before implementing the general public-link downloader, create a virtual environment and install the staged Phase 2 dependency:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-phase2.txt
```

If FFmpeg is missing, Codex should verify the current official Windows distribution or `winget` package before installing it. Do not silently download an arbitrary binary.

## Restore procedure

1. Copy the generated `AI-Canvas-Migration-*.zip` to the new laptop.
2. Extract it to a temporary folder.
3. Copy the extracted `workspace\AI Canvas` directory to the desired development location.
4. Copy the extracted `project-data\AI Canvas Projects` directory to `%USERPROFILE%\Documents\AI Canvas Projects`.
5. Either re-enter API keys through **Settings** in the app, or securely copy `settings.json` separately to `%LOCALAPPDATA%\AI Canvas\settings.json`.
6. Never upload an archive containing `settings.json` to a public repository or an unencrypted shared location.

The source Git repository currently has no initial commit and all project files are untracked. A normal Git clone is therefore **not sufficient**. Move the generated bundle or the entire workspace directory.

## Run the app

From the restored workspace:

```powershell
py -3 prototype\server.py
```

For safe end-to-end testing without contacting OpenAI or Gemini:

```powershell
py -3 prototype\server.py --mock-ai
```

Open `http://127.0.0.1:4173/`.

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:4173/api/health
```

Do not use `python -m http.server`; it does not provide the project, provider, drafting, export, or video APIs.

## Current architecture

- `prototype/index.html` — dependency-free application shell.
- `prototype/styles.css` — canvas, panels, projects, prompt editor, and video UI.
- `prototype/app.js` — canvas state, media import, annotations, prompt drafting, persistence, frame extraction, and export.
- `prototype/server.py` — same-origin static/API server, credentials, project folders, provider adapters, exports, and direct-video downloading.
- `AI_CANVAS_MVP_SPEC.md` — product requirements and Phase 2 design.
- `TECHNICAL_SPIKE_RESULTS.md` — earlier interaction-spike results; some limitations listed there are now outdated.

The application intentionally has no frontend build step and currently uses only the Python standard library at runtime.

## Completed and tested

Phase 1:

- Infinite canvas image paste/import, pan, zoom, move, proportional resize, labels, and marquee multi-selection.
- Rapid region annotation with keyboard workflow, editable/movable/resizable regions, multi-region selection, delete, duplicate, nudge, layer ordering, undo, and redo.
- OpenAI and Gemini provider settings stored outside projects.
- Vision-drafting request contains the objective, drafting instructions, compact filename, raw instruction, and cropped image—not the original source image.
- Editable drafted prompt with restore, regenerate, retry, manual edits, persistence, and stale-state warnings.
- Project creation, rename, Figma-like tabs, recent-project restore, autosave, duplicate, delete confirmation, and missing-media diagnostics.
- Timestamped export inside the active project, optional prompt copy/folder opening, compact names such as `R01A.png`, and atomic server-side validation.

Direct API/filesystem tests passed for:

- Project create/load/duplicate/delete.
- Remembering the active/open project IDs.
- Valid export creation.
- Rejection of exports whose prompt omits a manifest filename.
- Video persistence and HTTP byte-range serving (`206 Partial Content`).
- Mixed video package output containing `prompt.md`, `manifest.json`, and `V01.mp4`.

## Video phase checkpoint

Implemented in code:

- Local video files can be imported, dragged, and persisted as canvas assets.
- Pasting a **direct public video-file URL** calls the local downloader and saves the result in the active project's `media/` directory.
- Direct URL formats include MP4, WebM, MOV/M4V, and MKV.
- Private, loopback, link-local, reserved, and multicast targets are rejected to reduce server-side request-forgery risk.
- Video playback uses a same-origin media endpoint with byte-range support.
- Video references use a whole-video instruction rather than a spatial rectangle.
- AI drafting creates a four-frame contact sheet sampled across the clip and pairs it with the compact video filename and instruction.
- The current frame or 4/8/12 evenly distributed frames can be extracted as standard image assets.
- Extracted frames now record their source-video ID and timestamp in memory.
- Referenced videos export under compact names such as `V01.mp4`.

Important checkpoint: the last video edits were paused immediately after adding source-video IDs/timestamps to extracted frames and adding image-crop load rejection. Those last edits still require a fresh syntax check and UI verification.

## Public video-page downloader: next implementation

The app does **not** yet support arbitrary page URLs such as YouTube, Vimeo, TikTok, or Instagram. Do not build site extractors from scratch. Integrate the open-source `yt-dlp` project behind a narrow local adapter.

Recommended design:

1. Keep the current direct-file downloader as the fast path.
2. Add a `yt_dlp.YoutubeDL` Python adapter for supported public page URLs.
3. Resolve metadata first and immediately create a canvas placeholder with `resolving`, `downloading`, `processing`, `ready`, `failed`, or `cancelled` status.
4. Download into a project-local temporary directory, enforce configured size/duration limits, and atomically rename the completed file into `media/`.
5. Expose local job endpoints for create, status/progress, cancel, and retry. Never block the HTTP request for the entire download.
6. Store source URL, extractor name, title, duration, selected format, retrieval time, and failure details in the project manifest.
7. Use FFmpeg only when merging/remuxing/proxy generation is required; report clearly when it is unavailable.
8. Do not pass browser cookies by default. Do not bypass authentication, DRM, paywalls, geographic restrictions, or source terms.
9. Preserve manual direct-file import and local export when a source is unsupported.
10. Add controlled tests using a small permitted public fixture and mock extractor responses. Never rely on a private or copyrighted production URL in automated tests.

Suggested server boundary:

- `POST /api/projects/{id}/video-jobs` — validate URL and create a background job.
- `GET /api/projects/{id}/video-jobs/{jobId}` — metadata, progress, state, and error.
- `DELETE /api/projects/{id}/video-jobs/{jobId}` — cancel.
- `POST /api/projects/{id}/video-jobs/{jobId}/retry` — retry a failed/cancelled job.

The current `POST /api/projects/{id}/videos/import-url` direct-file endpoint should remain available.

## Immediate continuation checklist

When development resumes:

1. Run Python and JavaScript syntax checks.
2. Inspect the last edits around `extractVideoFrames`, `cropAnnotation`, reference-list error rendering, and export manifest frame metadata.
3. Finish the missing-media fallback card and ensure extracted-frame timestamps are written to `manifest.json`.
4. Restart `prototype/server.py --mock-ai` and verify the browser UI with a small locally owned MP4.
5. Test import, move/resize, whole-video instruction, save/reopen, current-frame capture, batch extraction, contact-sheet drafting, and mixed export.
6. Update `prototype/README.md` after the video UI passes.
7. Integrate yt-dlp using the adapter/job design above.
8. Add an initial Git commit before relying on Git-based migration or collaboration.

## Known limitations and cautions

- General video-page downloading is not implemented yet.
- Download progress/cancel/retry/resume UI is not implemented yet.
- The current video AI fallback analyzes sampled visual frames; it does not analyze audio.
- Real provider drafting requires the user's own API keys.
- Settings use readable local JSON by design; treat it as a secret.
- The prototype is not yet packaged as a Windows executable.
- A previous in-app-browser session was stuck on a cached localhost connection-error page, so the newest UI changes were not browser-verified in that session. This was a browser-control limitation, not an observed application-server failure.
