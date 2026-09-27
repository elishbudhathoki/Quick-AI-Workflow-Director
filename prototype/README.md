# AI Canvas interaction spike

This local browser prototype validates the canvas, export, and reference-map workflows before a production stack is selected.

## Run locally

From a fresh clone, set up the isolated environment, then run the local application server:

```sh
python setup.py
python start.py
```

The launcher opens `http://127.0.0.1:4173`. It supports Windows, macOS, and Linux desktops.

On Windows, `Restart-AI-CanvasServer.cmd` is a legacy start shortcut. It no longer kills whatever is listening on port 4173. Stop the running app with Ctrl+C in its server terminal before starting another copy.

On startup, the app scans the managed projects root and automatically loads the most recently updated project. If no managed project exists, it creates and loads an `Untitled project` folder. Browser-local recovery is used only when the project service is unavailable or when seeding that first managed project. Pasted and imported images autosave into the active project's `media/` directory.

Do not use `python -m http.server` for this app. That command serves the interface but does not provide the `/api` routes needed for provider setup, projects, or AI drafting. If provider setup reports that the local server is unavailable, stop the static server, run `prototype/server.py`, and refresh the page.

For a full end-to-end test that never contacts an AI provider, use:

```sh
python start.py --mock-ai
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

The in-progress video phase supports local video import, direct public video-file URLs, public video-page URLs through the local `yt-dlp` adapter, whole-video instructions, sampled contact-sheet drafting, frame extraction, same-origin range playback, persistence, and compact video export names such as `V01.mp4`. Public page downloads run in the background; the Prompt panel shows resolving, downloading, processing, ready, failed, and cancelled states with cancel and retry controls. The downloader never supplies browser cookies or bypasses authentication, DRM, paywalls, or source restrictions.

Video job records are saved in each project folder. If the server restarts while a download is active, AI Canvas restores the job, tells `yt-dlp` to continue from its existing partial file where the source supports it, and restores the job card when that project is reopened.

Exports keep image crops at source resolution and video frames as full-resolution lossless PNG files. Public video downloads request the best available streams and retain the 240 MB local safety limit.

## Reference maps

Select an image or crop, choose Canny, Outline, Depth, Human pose, Soft edge, Normal, or Scribble, then press **Generate & export maps**. Animal pose is available with a ComfyUI workflow. Each successful map is a PNG in a timestamped `exports/maps_*` folder and an image asset on the canvas. **Download maps ZIP** downloads the batch; selecting an individual map offers **Download image**. **Add my map image** attaches an existing PNG, JPEG, or WebP map to the selected reference, with its map type and source recorded in the project.

Double-click an image on the canvas to open the circular quick-map menu. Existing maps show their actual thumbnails and open on click; a missing map starts generation. A temporary preview tile occupies its canvas position while generation runs, then the finished map appears there. Pasting a direct PNG, JPEG, or WebP link downloads the image into the current project with the same loading tile. Pasted video links show the loading tile too; public video-page downloads display their measured percent when the source reports a total.

Built-in Canny uses full-resolution OpenCV gradients and Canny edge detection. Outline uses `controlnet-aux` Lineart, depth uses the Apache-licensed Depth Anything V2 Small model, Human pose uses OpenPose body, hands, and face, Soft edge and Scribble use HED, and Normal uses NormalBae. The built-in learned models cache their downloaded weights and use bounded inference sizes; generated built-in PNGs retain source dimensions. Depth batches also include a 16-bit grayscale depth PNG for further editing. Images are processed locally, without a paid model API.

To use your own map model or preprocessor, select **My ComfyUI models** in Reference maps. Run ComfyUI locally, enter its address (normally `http://127.0.0.1:8188`), and choose a workflow exported from ComfyUI in **API format**. The workflow needs a `LoadImage` input and a `SaveImage` or `PreviewImage` output. Select their nodes and save the workflow for any map type. For Animal pose, use the [ControlNet Auxiliary Preprocessors](https://github.com/Fannovel16/comfyui_controlnet_aux) `AnimalPosePreprocessor` with an AP-10K pose estimator. AI Canvas saves each workflow inside that project, uploads the chosen reference to local ComfyUI, queues the workflow, and imports its output map. The model, preprocessor, and settings come from the workflow, so install and configure them in ComfyUI. ComfyUI's [self-hosted API routes](https://docs.comfy.org/development/comfyui-server/comms_routes) document the local interface.

Install the optional learned map dependencies in the project virtual environment:

```sh
python setup.py --maps
```

Human pose reports when no person is detected. Animal pose requires ComfyUI and is unavailable in the built-in engine. Model maps may take longer on first use, especially on a CPU. A ComfyUI workflow's output keeps its own pixel dimensions, which may differ from the source. The export setting uses source quality by default: crops and video frames keep source dimensions and frame images use PNG.

## Remaining work

- Live OpenAI and Gemini requests require the user's own provider keys and were not executed during automated testing.
- No production canvas framework or desktop wrapper.
- No groups, notes, or context-set inclusion controls yet.
- Destination delivery, scene-change frame extraction, and further map types such as semantic segmentation remain planned.
- Setup installs an FFmpeg binary through `imageio-ffmpeg`; unusual public sources can still require source-specific support.
- The Phase 1 prototype intentionally uses a readable local settings file for keys rather than an OS credential vault.

The current slice validates the complete fast annotation/editing loop, recoverable deletion, command history, coordinate correctness, crop regeneration, editable provider drafting, timestamped export, local project restoration, and the initial video persistence/export foundation.
