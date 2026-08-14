# AI Canvas — Milestone 0 Interaction Spike Results

Date: 2026-08-12  
Status: Interaction model validated; production stack decision provisional  

## Scope

This spike tests the highest-risk product behavior before a desktop framework or production canvas library is selected:

```text
Import/paste → zoom → R → drag region → type instruction → Enter → draw next region
```

It also tests source-coordinate crops, deterministic crop filenames, natural-language instruction parsing, crop-only prompt compilation, and a synthetic canvas load.

## Prototype

The runnable prototype is in [`prototype/`](./prototype/).

Run from the workspace root:

```powershell
C:\Users\Leapfrog\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m http.server 4173 --directory prototype
```

Open `http://127.0.0.1:4173/`.

## Verified interaction

The following sequence passed in the in-app browser:

1. Import an image.
2. Press `R`.
3. Draw a jacket region.
4. Type `jacket without logo` and press Enter.
5. Draw a face region immediately without reselecting the Region tool.
6. Type `face and hair, ignore background` and press Enter.
7. Enter an objective and prompt-formatting instruction.
8. Draft the prompt.

Observed output:

- Two independent crop cards.
- `REF_01_A_WARDROBE_jacket.png`.
- `REF_01_B_CHARACTER_IDENTITY_face-and-hair.png`.
- Jacket interpreted as Wardrobe.
- Logo converted into an avoid instruction.
- Face and hair interpreted as Character identity.
- Background converted into an avoid instruction.
- References grouped into Wardrobe and Character Identity sections.
- No original source filename or source image included in the compiled prompt.
- Region mode remained active after each Enter.
- No browser errors or warnings.

## Synthetic load check

Benchmark URL:

```text
http://127.0.0.1:4173/?benchmark=100
```

Observed in the current environment:

| Check | Result |
|---|---:|
| Image cards | 100 |
| Annotation overlays | 200 |
| Cached synthetic initialization | 23 ms |
| Fit-to-board zoom | 19% |
| Zoom interaction | 19% → 37% |
| Browser warnings/errors | 0 |

The 23 ms result uses the same cached SVG source repeatedly. It is a regression baseline for DOM creation, not a realistic high-resolution media benchmark. The production spike must repeat this with varied large bitmap files, thumbnail generation, memory sampling, and viewport culling.

## Issues found and corrected

1. The Region-mode hint initially ignored its hidden state because a CSS display rule took precedence.
2. Instructions such as `face and hair, ignore background` initially retained punctuation before the exclusion, producing double commas in drafted text.
3. Prompt-formatting instructions were initially appended but did not visibly affect local output. The deterministic spike compiler now groups references into semantic sections when sectioned formatting is requested.

## Provisional production recommendation

- **Desktop shell:** Tauri 2.
- **Frontend:** React + TypeScript.
- **Canvas approach:** Custom transformed DOM/SVG scene for the first production iteration, with viewport culling and level-of-detail thumbnails.
- **State:** A small explicit store with undoable commands; avoid coupling domain data to a canvas library.
- **Persistence:** SQLite plus a project-relative media and derived-crop directory.
- **Image work:** Background workers or native commands for thumbnails, crops, metadata, and hashing.

The DOM/SVG approach is provisional because it already supports the required interaction cleanly at the MVP target. A heavier rendering engine should only be introduced if varied high-resolution benchmark data shows a measurable need.

## Deliberate prototype limitations

- No project persistence.
- No undo implementation.
- No region resize handles.
- No real vision-model description drafting.
- No provider APIs.
- No ZIP export.
- No high-resolution memory benchmark.
- The deterministic parser supports common fast instructions but is not a substitute for the planned image-aware drafter.

## User feel review

Before production scaffolding, test the clean prototype and judge only the interaction:

- Does the paste/import experience feel immediate?
- Is `R` → drag → type → Enter natural?
- Is it obvious that Enter allows another annotation immediately?
- Are the yellow region labels readable without becoming visually noisy?
- Does the right panel stay out of the way during capture?
- Would a different shortcut or annotation color feel better?

Any friction found here should be corrected in the prototype before the behavior is rebuilt in the production stack.
