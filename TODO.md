# AI Canvas TODO

## Desktop source release

- [x] Add Apache-2.0 source license, root setup guide, storage notes, and third-party model notices.
- [x] Add cross-platform `setup.py` and `start.py`; keep user projects and settings outside the clone.
- [x] Verify a new Windows virtual environment installs core and learned-map packages, runs the server/Canny smoke check, and generates Human pose.
- [x] Add local Host/Origin checks and stop the Windows helper from killing unrelated port listeners.
- [x] GitHub Actions clean-clone matrix passed on Windows, macOS, and Linux with Python 3.11–3.13; optional learned-map packages imported on all three operating systems.
- [ ] Test the browser UI and optional maps on a real macOS and Linux desktop, including GPU/CPU fallbacks.
- [ ] Publish a public release tag after cross-platform checks and repository visibility review.

## SOL handoff: local video frame picker

### 2026-09-27 implementation update

- Fixed Human pose's missing `matplotlib` dependency and confirmed a 736×1103 portrait now produces a 736×1103 pose map.
- Map generation placeholders and finished map cards now use the selected source card's canvas dimensions and position. The placeholder shows a soft preview of the source while processing.
- Added a whole-video range navigator above a local frame-detail filmstrip. The picker reads the source frame rate from the local server, steps at that rate, and stops assigning a live frame to a thumbnail with a different timestamp.
- Browser-checked the user's 24 fps, 248-frame clip: jumping to 5 seconds rebuilt the detailed strip around 5 seconds, and Next frame moved to 5.041 seconds. The server metadata endpoint reported 24 fps and 248 frames.
- Restored plain video-card double-click while keeping Ctrl + double-click for import and empty-canvas double-click for templates. A capture-phase second-pointer check survives card re-rendering during selection.
- Source-quality image export is now the default. Extracted frames store the actual decoded timestamp, and crop manifest records include source-video ID/timestamp and derived-map provenance.
- Browser-checked synthetic 3-second landscape, 27-second portrait, and 90-second landscape clips. The picker opened before thumbnails filled; reopen reused cached thumbnails. Exported frame dimensions matched the three sources (640×360, 360×640, 320×180). A 90-second clip selected at 40.909 seconds produced sourceTimestampMs 40909.
- Still validate with user-owned real-world clips, especially unusual codecs, audio tracks, and long 4K media. Synthetic checks do not settle the user-reported interaction concern.

Priority: high. The current implementation is not acceptable as a user experience. Do not spend time polishing this surface until its interaction and performance are reliable.

### User-reported outcome

- The frame picker does not behave like the intended CapCut/TikTok interaction. It has been slow and buggy in user testing.
- Earlier, opening required Ctrl+double-click; the shortcut was changed to plain double-click, but the user still reported that the picker either did not open or did not show the updated UI.
- Treat user testing as the source of truth. Do not mark this resolved merely because a local automation check succeeds.

### Product goal

Create a focused reference-frame selector, not a full video editor:

- Plain double-click on a canvas video opens it. **Open frame picker** in the selected-video inspector remains an accessible fallback.
- The large player plays the project's local downloaded/imported video immediately; it must never depend on a remote URL.
- The video image above the strip, the selected filmstrip thumbnail, and the exported frame all represent the same timestamp from the same local source.
- A fixed center playhead stays still while the thumbnail strip moves beneath it.
- Clicking, horizontal dragging, trackpad scrolling, and arrow keys make scrubbing feel direct and responsive.
- Timeline scale changes continuously from the whole video to individual-frame precision through pinch or Ctrl + wheel; there are no Overview/Detail/Frames mode tabs.
- Export frame sits beside the selected timestamp and uses the existing highest-quality/source-quality export preference; never export the low-resolution thumbnail.

### Acceptance checks

- [x] Plain double-click reliably opens the picker on a video card, even after drag/select interactions and after a browser refresh.
- [x] Inspector fallback opens the same picker every time.
- [x] The modal is visibly open and focused immediately; video controls can play/pause without waiting for filmstrip work.
- [x] The player shows the current frame immediately; the detailed strip progressively fills with thumbnails captured at their labelled timestamps without blocking input.
- [x] Timeline remains responsive while thumbnails decode: click, drag, wheel/trackpad, keyboard left/right, and close all work.
- [x] Automatic wheel/pinch zoom changes the bounded sampling window around the fixed playhead without mode tabs.
- [x] Moving quickly across a clip cancels obsolete thumbnail generations instead of queuing them indefinitely.
- [x] Reopening a video uses cached preview data where valid and feels substantially faster than first open.
- [x] Synthetic source-quality exports matched source dimensions and recorded the actual decoded timestamp; real-world validation remains open below.
- [x] Confirm a local scrub proxy is generated and used when FFmpeg is available; original-source export remains on the retained source file.
- [x] Tested synthetic short, 27-second portrait, and 90-second clips; first open was immediate and reopen reused filmstrip thumbnails.
- [ ] Confirm the same behavior on user-owned clips with real codecs and 4K media.

### Latest verification

- Tested against a real local 2160×3840 WebM of approximately 65 MB and 27 seconds.
- The modal opens synchronously on the second click; the local video reached ready state 4 and displayed the current frame without waiting for the filmstrip.
- The current player frame is visible immediately; detailed thumbnails decode progressively from their labelled timestamps.
- The 65 MB source produced a cached 7.2 MB project-local scrub proxy. The picker loaded that proxy while the export path continued to reference the original source.
- Rapid jumps across five non-adjacent thumbnails resolved to the requested timestamps every time. Smooth auto-scroll was removed because it could issue a competing seek after a click.
- Frame-step moved from 0 to 0.033 seconds; automatic timeline zoom produced a bounded local window without changing modes.
- A portrait 2160×3840 source now fits as a 194×345 preview inside the 1010×346 stage with no cropping.
- A clicked timeline thumbnail and the visible video resolved to the same 17.501169-second timestamp with less than one microsecond of measured difference.
- Cached reopen restored all 12 overview thumbnails during the first 60 ms check.
- Still requires user validation plus separate short-clip, long-clip, and exported-dimension checks before final closure.

### Current code and known risks

- `prototype/app.js` contains `openVideoFrameViewer(asset)`, thumbnail cache state, video-card double-click listeners in `renderAsset()`, and a workspace-level double-click handler.
- `prototype/index.html` contains `#videoFrameViewer`; `prototype/styles.css` contains `.video-frame-viewer*` and `.video-filmstrip*`.
- Thumbnail decoding uses a separate hidden `<video>` pointed at the lightweight scrub proxy. It is cancellable and bounded, but long-clip behavior and memory limits still need validation.
- Current event handling mixes direct card double-click listeners, workspace double-click delegation, and canvas pointer/drag behavior. Consolidate this into one reliable gesture path and ensure drag logic cannot swallow a genuine double-click.
- Current thumbnail cache is in-memory only and keyed by video/zoom/time bucket. Validate cancellation, cache invalidation, and memory limits before expanding it.
- Asset URL version query strings were added to bypass stale browser script/style caching. Keep a deliberate cache-busting or build-version strategy while this prototype has no bundler.

### Suggested implementation direction for SOL

1. Reproduce with browser devtools open; instrument modal-open, double-click, pointer-drag, video metadata, seek, and thumbnail timing events.
2. Simplify the opening path first: one canonical `openVideoFrameViewer(asset)` call; prevent canvas drag only when opening is confirmed.
3. Decouple player readiness from thumbnail generation. Render the modal and current source frame first; run previews in a cancellable queue with a generation/session token.
4. Generate only a bounded window of thumbnails for the active zoom; prioritize the current frame and its immediate neighbours. Never decode an entire video up front.
5. Keep the selected timestamp as the single source of truth. All player seeking, active thumbnail state, and export must read it.
6. Add lightweight performance logging or a test harness before considering the task done.

### Do not change while fixing

- Do not downgrade downloaded video, frame extraction, crops, or exports. Preserve the existing highest-quality/source-quality settings.
- Do not replace the local video source with a remote URL or with a filmstrip thumbnail.
- Do not remove the inspector fallback while double-click reliability is being fixed.

### Documentation already updated

- `AI_CANVAS_MVP_SPEC.md`, section **22.2 Local frame-picker experience**, defines the intended behavior and quality requirements.
- `UNSOLVED_ISSUES.md` contains the earlier opening/caching history; update its status when this handoff is genuinely resolved.

## Deferred

- [ ] Add semantic segmentation maps for scene regions and object categories.
- [ ] Add tile/detail, straight-line (MLSD), face-landmark, and inpainting-mask map workflows; evaluate which deserve fast built-in processors versus ComfyUI presets.
- [ ] Validate Animal pose with a live ComfyUI AP-10K workflow and representative animal images; consider a built-in animal pose model if the workflow path proves cumbersome.
- [ ] When full text-to-image generation is added, connect its job lifecycle to the reusable canvas loading tile so the final image replaces the placeholder in place.
- [ ] Metadata confirmation before large public-page downloads.
- [ ] Scene-change keyframe extraction.
- [ ] Contact-sheet generation controls and extraction progress/cancellation.
