# AI Canvas interaction spike

This dependency-free browser prototype validates the highest-risk interaction before the production stack is selected.

## Run locally

From the workspace root, run the local application server:

```powershell
py -3 prototype\server.py
```

Then open `http://127.0.0.1:4173`.

On startup, the app scans the managed projects root and automatically loads the most recently updated project. If no managed project exists, it creates and loads an `Untitled project` folder. Browser-local recovery is used only when the project service is unavailable or when seeding that first managed project. Pasted and imported images autosave into the active project's `media/` directory.

Do not use `python -m http.server` for this app. That command serves the interface but does not provide the `/api` routes needed for provider setup, projects, or AI drafting. If provider setup reports that the local server is unavailable, stop the static server, run `prototype/server.py`, and refresh the page.

For a full end-to-end test that never contacts an AI provider, use:

```powershell
py -3 prototype\server.py --mock-ai
```

For image-aware drafting, expand **AI settings**, choose OpenAI or Google Gemini, paste that provider's key, and press **Save & connect**. Each provider keeps its own key in the local AI Canvas app settings file under `%LOCALAPPDATA%\AI Canvas\settings.json`. This file is outside all project folders and is never included in project saves or exports. Environment variables remain supported as an optional fallback.

## Test path

1. Copy an image from any application.
2. Paste it with Ctrl+V, or Ctrl+double-click the canvas to choose one or more images.
3. Zoom with the wheel and pan with Space + drag.
4. Press `R`.
5. Drag a rectangle on the image.
6. Type `jacket without logo` and press Enter.
7. Press `V`, then drag the annotation to move it or drag its handles to resize it.
8. Select the image and drag a corner handle to resize it proportionally.
9. Use Delete, Ctrl+Z/Ctrl+Y, Ctrl+D, arrow-key nudging, and Ctrl+[/Ctrl+] layer ordering.
10. Double-click an annotation (or press Enter while selected) to edit its instruction.
11. Enter an objective and prompt-drafting instructions in the right panel.
12. Press `+` in the top-left project tab strip and rename the new tab inline. Switch between visible tabs in one click; closing a tab keeps its folder. Each project receives a human-named folder with `project.json`, `media/`, and `exports/`, and settled changes autosave there.
13. Press **Analyze & Draft** to send each crop with only its compact filename and raw user instruction to the configured vision model, or choose **Draft without AI** for the deterministic local compiler. The local canvas label is not sent, and there is no semantic-role field.
14. Press **Export package** to write `prompt.md`, `manifest.json`, and compactly named crops such as `R01A.png` into a timestamped directory under the active project's `exports/` folder. In **Settings → Export settings**, independently choose whether export also copies the prompt and opens that timestamped package folder. Export never asks for another destination; without an active project, it directs you to create or open one first.
15. Load the saved project from the **Projects** tab to restore its canvas, annotations, prompt fields, and managed source images.

The prototype keeps a fast browser-local autosave while you work and provides explicit project-folder saves for durable organization. It creates crop previews from source-coordinate annotations and materializes pasted/imported media inside the active project's folder. Image-aware drafting supports OpenAI and Gemini through a same-origin local server, provider-specific models, strict structured output, and exact crop-filename validation. Drafted prompts remain editable and are marked stale rather than deleted when their inputs change. Resizing a canvas image does not resample or alter its source crop.

The in-progress video phase supports local video import, direct public video-file URLs, whole-video instructions, sampled contact-sheet drafting, frame extraction, same-origin range playback, persistence, and compact video export names such as `V01.mp4`. Arbitrary public video-page URLs are not supported yet; the next step is the yt-dlp adapter documented in `MIGRATION_HANDOFF.md`.

## Deliberate limitations

- Live OpenAI and Gemini requests require the user's own provider keys and were not executed during automated testing.
- No production canvas framework or desktop wrapper.
- No groups, notes, or context-set inclusion controls yet.
- General video-page downloading through yt-dlp, background progress/cancel/retry, and FFmpeg processing are not integrated yet.
- The Phase 1 prototype intentionally uses a readable local settings file for keys rather than an OS credential vault.

The current slice validates the complete fast annotation/editing loop, recoverable deletion, command history, coordinate correctness, crop regeneration, editable provider drafting, timestamped export, local project restoration, and the initial video persistence/export foundation.
