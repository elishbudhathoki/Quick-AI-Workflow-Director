# Unsolved issues

## Canvas video frame picker is unreliable and does not meet the intended UX

**Status:** Rebuilt and ready for user validation. Keep open until the user confirms the real interaction and the remaining short/long-clip and export-quality checks pass.

### Latest rebuild

- Consolidated opening to one capture-phase delegated double-click path plus the inspector fallback.
- The large project-local video opens before thumbnail work and remains the single selected-frame source.
- Scrubbing directly seeks the visible video through an animation-frame throttle; it no longer schedules filmstrip regeneration on every seek.
- One continuous automatic timeline scale replaces Overview, Detail, and Frames tabs; pinch/Ctrl + wheel zooms around the playhead and ordinary scroll scrubs.
- A project-local FFmpeg scrub proxy is generated in the background when available and is used for preview seeking while export keeps the original source.
- Thumbnail work prioritizes the current frame, progressively fills in the background, cancels obsolete generations, and reuses cached windows.
- The picker UI was rebuilt around a fixed playhead, direct drag/scroll scrubbing, frame-step controls, source metadata, and an adjacent full-quality Export frame action.
- Explicit decoded-aspect fitting prevents portrait or landscape video from overflowing or being cropped by the preview stage.

### Intended behavior

Double-clicking a video card on the canvas should open a large, focused frame picker inspired by CapCut/TikTok:

- The large local video is the only selected-frame preview and export source.
- A thumbnail filmstrip from that same video appears beneath it.
- A fixed center playhead indicates the selected frame.
- Clicking or scrolling the filmstrip updates the large video frame.
- Left/right arrows step approximately one frame (1/30 second).
- The viewer exposes only Play/Pause, timestamp, Export frame, and Close.

### Resolution

The root cause was stale browser caching of unversioned `app.js` and `styles.css`. `index.html` now uses versioned asset URLs so refreshed pages load the current frame-picker code. Browser verification confirmed both the explicit **Open frame picker** action and canvas double-click open the large filmstrip viewer with no console errors. The explicit action remains the discoverable primary entry point; double-click is a shortcut.

### What was attempted

- Workspace-level `dblclick` handling for `.asset` video cards.
- A direct `dblclick` listener attached when `renderAsset()` creates each video card.
- A `#videoFrameViewer` modal containing the large video and filmstrip.
- JavaScript syntax checks pass (`node --check prototype/app.js`).

### Investigation notes

- The local server must be launched by the Windows user, not from Codex's restricted test environment. A Codex-launched server cannot write to `%USERPROFILE%\Documents\AI Canvas Projects` and shows `Permission denied ... project.json.tmp`.
- The ordinary local server was confirmed to serve the latest `app.js` and frame-viewer markup, but the interaction still did not visibly open for the user.
- Start by checking browser console errors and whether the canvas receives the double-click after its pointer/drag handling runs. Consider an explicit temporary “Open frame picker” action in the selected-video inspector to isolate the modal implementation from the canvas gesture.

### Relevant code

- `prototype/app.js`: `renderAsset`, `openVideoFrameViewer`, workspace pointer and double-click handlers.
- `prototype/index.html`: `#videoFrameViewer`.
- `prototype/styles.css`: `.video-frame-viewer` and `.video-filmstrip*`.
