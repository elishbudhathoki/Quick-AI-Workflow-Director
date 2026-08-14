# AI Canvas — MVP Product Specification

Status: Planning baseline  
Product type: Local-first Windows desktop utility  
Initial audience: A single creative user using their own provider API keys  
Initial focus: Image generation and image editing workflows  

## 1. Product summary

AI Canvas is an AI-powered visual context compiler for creative work. The user collects images on an infinite canvas, marks the exact regions that matter, writes a direct natural-language instruction for each crop, and adds a simple objective. An image-capable language model inspects each crop together with its instruction, understands how it should influence the objective, and drafts a detailed prompt that references the exact exported crop filenames.

The application removes three repetitive tasks:

1. Re-uploading and renaming reference files for every prompt.
2. Re-explaining which part of each reference should be used or ignored.
3. Reformatting the same visual context for different AI providers.
4. Manually studying each reference to translate its visible characteristics into prompt language.

The project canvas is the source of truth. Provider requests are generated outputs, not the project format.

Phase boundaries:

- **Phase 1:** Complete local image-reference canvas, image-aware prompt drafting, and manual local export.
- **Phase 2:** Video link/file ingestion, whole-video references, frame extraction, video-aware drafting, and optional destination delivery to ChatGPT, Gemini, or other tools through supported integration adapters.
- **Phase 3:** Local derived reference maps from images and extracted video frames: edges, depth, pose, line art, normals, and segmentation.

## 2. Product principles

1. **Local until analyzed.** Imported media remains local unless the user explicitly starts **Analyze & Draft**; Phase 1 uploads only the selected crops to the configured drafting LLM.
2. **Point first, explain second.** Selecting an exact image region should require less effort than describing it in prose.
3. **Structured beneath the canvas.** Every visual annotation maps to explicit data that can be compiled and validated.
4. **Provider-neutral projects.** Projects must remain usable if providers, models, or APIs change.
5. **Preview before cost.** The user sees the exact prompt, files, and selected provider before a request is submitted.
6. **No destructive annotation.** Original media is never painted over or modified.
7. **Fast repetition.** Templates, duplication, keyboard shortcuts, and remembered defaults are first-class features.
8. **Canvas first.** The interface should feel as immediate and lightweight as a modern collaborative whiteboard: minimal chrome, direct manipulation, and no unnecessary mode changes.
9. **Progressive disclosure.** The fast path exposes only what the user needs now; advanced metadata and provider options remain available without crowding the canvas.
10. **Never wait to capture intent.** Local edits render optimistically and save immediately; AI drafting, crop processing, and network activity continue in the background.

## 3. MVP goals

The MVP must allow a user to:

- Create and reopen local projects.
- Paste or import images onto an infinite canvas.
- Select, move, resize, duplicate, group, reorder, and delete images with complete undo and redo support.
- Mark rectangular regions inside images.
- Create a region annotation with one shortcut, one drag, one natural-language instruction, and Enter.
- Select, move, resize, rename, re-instruct, hide, include/exclude, and delete an existing annotation without recreating it.
- Convert short instructions such as `jacket without logo`, `use these colors and gradients`, or `use this art style` into a visually grounded interpretation and detailed prompt contribution.
- Create reusable character, scene, and style templates.
- Write a primary creative request, output constraints, and instructions controlling how the final prompt should be written and formatted.
- Use an image-capable LLM to inspect all included crops and draft a detailed, provider-neutral prompt that combines them with the objective.
- Preview a provider-neutral compiled reference package.
- Automatically generate stable filenames and one outbound crop for each included annotation.
- Export the same package for manual use in ChatGPT, Gemini, or another tool.
- Configure separate bring-your-own API keys for multiple drafting providers, choose a provider/model per draft, and keep every provider setup available between sessions.
- Save prompt-drafting history.

## 4. Explicit non-goals for the MVP

- Collaborative editing or multiplayer cursors.
- Cloud accounts, subscription billing, or project synchronization.
- Full video timeline editing.
- Vector illustration or general-purpose whiteboarding.
- Browser automation of consumer AI websites.
- Direct dispatch to ChatGPT, Gemini, or generation APIs; this is Phase 2.
- Automatic subject segmentation or background removal in Phase 1 or Phase 2; this is introduced as an optional derived map in Phase 3.
- A marketplace for templates or provider adapters.
- Mobile or tablet applications.
- Training or fine-tuning custom models.

## 5. Primary user workflow

### 5.1 Create a project

The user creates a named project and chooses an optional template. The app creates a project database and an associated media directory.

### 5.2 Capture references

The user can:

- Paste an image from the clipboard.
- Drag one or more image files onto the canvas.
- Use an Import button and file picker.
- Duplicate an existing reference card.
- Insert a saved library item or template.

Each imported asset immediately receives an internal ID. Its display name may change, but its identity must remain stable.

### 5.3 Annotate a reference

The primary annotation path is deliberately minimal:

1. Paste an image with Ctrl/Cmd + V.
2. Zoom to the desired detail.
3. Press `R` to activate the Region tool.
4. Drag a rectangle around the desired subject or detail.
5. A small text field appears next to the region with keyboard focus already inside it.
6. Type a direct instruction such as `jacket without logo`.
7. Press Enter to save it and immediately continue drawing another region.

No inspector interaction or form completion is required in the fast path. Escape exits rapid annotation mode. A generated short label may be edited locally for easier canvas navigation, but it is not sent to the drafting model.

The app preserves the user's raw instruction and drafts structured meaning from it. Drafting may happen immediately after entry or during compilation, but it must never delay saving the region.

Example:

- Raw instruction: `jacket without logo`
- Drafted label: Jacket
- Suggested role: Wardrobe
- Drafted use: Use the jacket shown in this crop as the wardrobe reference.
- Drafted avoid: Do not include or reproduce the logo.
- Drafted description: A jacket reference isolated from the source image; use its visible design while excluding the logo.

The drafted fields remain editable. The raw instruction is always retained so the user can see exactly what the draft was based on.

An entire image may be used by drawing a region around the full image. The export workflow remains crop-based; the locally stored original is not included automatically.

### 5.4 Assemble a context set

The user selects reference cards, groups, or saved templates and adds them to the current context set. The context set is the exact subset compiled for a prompt draft; unrelated items may remain elsewhere on the canvas.

### 5.5 Write the request

The user enters:

- Main creative objective.
- Prompt drafting instructions, such as `Write this as a structured cinematic prompt with separate Character, Wardrobe, Environment, and Lighting sections`.
- Output operation: analyze, generate image, or edit image.
- Output count and aspect ratio where supported.
- Positive constraints.
- Negative constraints.
- Optional custom provider instructions.

Prompt drafting instructions may be saved as reusable local templates. The template shelf supports click-to-apply, drag-and-drop onto the instruction field, and importing plain-text or Markdown (`.txt`/`.md`) files. Templates are shared locally across projects and never uploaded merely by saving or browsing them.

### 5.6 Analyze references and draft the prompt

The user presses **Analyze & Draft**. The app sends the following to the configured image-capable LLM:

- The main objective.
- Every included crop, each identified by its deterministic export filename.
- The raw annotation attached to each crop.
- Its assigned semantic role, such as Color treatment or Visual style.
- Global prompt drafting and formatting instructions.
- A strict response schema for crop descriptions, use/avoid rules, and the final prompt.

The model must understand the relationship between the inputs. For example, `Colors and gradients` means that the first crop should control palette and gradient behavior, not subject matter or layout. `Art style` means that the second crop should control rendering language, not character identity.

### 5.7 Preview and export

The app validates the context, generates crops and filenames, and shows:

- Drafting provider and model.
- Files that were analyzed and will be exported.
- Compiled prompt.
- Drafted text description for every exported crop.
- Exact local export folder and filenames.
- Warnings and unsupported options.

The user can edit the draft, then press **Export Package**. Phase 1 writes the prompt and labeled crops to a local folder and provides **Copy Prompt** and **Reveal in Folder** actions. No final image-generation request is made.

### 5.8 Review prompt drafts

The result appears in a draft panel. The user may:

- Save the prompt as a project revision.
- Duplicate the draft with modifications.
- Compare a draft with an earlier version.
- Open the exported request package.

## 6. Application layout

```text
+--------------------------------------------------------------------------+
| Project | Undo Redo | Template | Drafting model | Analyze & Draft        |
+----------+------------------------------------------------+--------------+
|          |                                                |              |
| Select   |                                                | Inspector    |
| Hand     |               Infinite canvas                  |              |
| Region   |                                                | Selection    |
| Note     |       [Character]   [Wardrobe]   [Lighting]     | Annotation   |
| Group    |                                                | Prompt       |
|          |                                                | Properties   |
| Library  |                                                |              |
+----------+------------------------------------------------+--------------+
| Context set: 8 references | 3 crops | Validation: Ready | Draft history   |
+--------------------------------------------------------------------------+
```

### 6.1 Top bar

- A visible Figma-like project tab strip beside the app name, with a prominent `+` action, one-click switching, inline rename on double-click, and tab closing that never deletes the underlying folder.
- Current template.
- Drafting provider and image-capable model selector.
- Analyze & Draft button.

### 6.2 Left toolbar

- Select tool.
- Hand/pan tool.
- Region annotation tool.
- Undo, redo, and clear-canvas actions.
- Note tool.
- Group tool.
- Asset library.

### 6.3 Canvas

- Infinite pan and zoom.
- Images, notes, groups, draft cards, and template instances.
- Lightweight role badges visible at normal zoom.
- Annotation regions visible when an image is selected or annotations are toggled on.
- A compact floating instruction field appears at the newly drawn region and is removed from the canvas after Enter commits the instruction.

### 6.4 Right inspector

The right area has persistent **Selection** and **Prompt** tabs. Selection content changes with the canvas selection, while the Prompt tab remains reachable at all times.

- Asset properties.
- Annotation role and instructions.
- Group or template properties.
- Prompt composer with objective, prompt drafting instructions, constraints, and output settings.
- Draft revision details when a prior draft is selected.

### 6.5 Bottom status bar

- Active context-set count.
- Generated crop count.
- Validation state.
- Background processing state.
- Draft history shortcut.

### 6.6 Minimal interaction quality bar

The application should feel closer to a lightweight canvas tool than a form-based AI dashboard.

- The canvas occupies most of the window and remains the visual focus.
- Paste, move, resize, annotate, type, group, and delete actions do not open modal dialogs.
- Advanced annotation properties are hidden until expanded or opened in the inspector.
- Selection feedback and tool-state changes appear immediately.
- Toolbars stay compact; context actions appear near the selection only when useful.
- Side panels can be collapsed with a shortcut and must not be required for rapid annotation.
- Background work uses subtle status indicators rather than blocking overlays.
- Provider setup always shows a compact state indicator: not connected, checking, connected, or error with an actionable message.
- Escape always provides a predictable way to leave the current temporary tool or input.
- Destructive canvas edits are handled through undo instead of confirmation dialogs whenever recovery is possible.
- Empty states teach the three-action core workflow: paste, mark, describe.
- Animations are short and functional. They clarify selection, panel changes, or draft arrival without slowing repeated work.

## 7. Core interactions

### 7.1 Canvas behavior

- Mouse wheel or trackpad: zoom around pointer.
- Space + drag or middle mouse drag: pan.
- Click: select one item.
- Shift + click: add or remove from selection.
- Drag on empty canvas: marquee selection.
- Delete: remove selected canvas objects immediately and offer Undo; do not show a confirmation dialog for recoverable canvas edits.
- Ctrl/Cmd + Z: undo.
- Ctrl/Cmd + Shift + Z or Ctrl/Cmd + Y: redo.
- Ctrl/Cmd + D: duplicate.
- Ctrl/Cmd + G: group.
- R: enter rapid Region annotation mode.
- Escape: close the annotation input or return to the Select tool.
- F: frame selected objects in view.
- 0: fit project to view.
- Ctrl/Cmd + double-click empty canvas: open the multi-image upload picker.

### 7.2 Clipboard import

- Pasting a supported bitmap creates an image card at the viewport center.
- Pasting multiple files lays them out in a simple grid.
- Pasting a URL creates a pending import card and downloads only after confirmation.
- Pasting text creates a note card.

### 7.3 Region annotation

- Regions are stored in source-image coordinates, independent of canvas zoom or card size.
- Moving or resizing the image card must not alter the region's source coordinates.
- Resizing a region updates the crop preview immediately.
- Regions can be temporarily hidden without deleting them.
- Each region receives a stable letter within its asset: A, B, C, and so on.
- Drawing a region immediately opens a focused, single-line instruction field next to it.
- Enter commits the raw instruction and keeps Region mode active so another region can be drawn without using the toolbar again.
- An empty instruction may be committed, but it produces a warning before compilation.
- The app suggests a short label and semantic role without forcing the user to choose them manually.
- Phrases containing exclusions, such as `without logo`, `no buttons`, or `ignore the background`, are separated into drafted avoid instructions.
- The user may edit all drafted values in the inspector, but this is optional for ordinary annotations.
- Each included region produces its own crop. The source image is retained locally for non-destructive editing but is excluded from outbound packages by default.

### 7.4 Selection, movement, resizing, and deletion

Editing fundamentals are part of the MVP, not post-MVP polish.

#### Image manipulation

- Clicking an image selects it and shows a clear outline with resize handles that remain a usable screen size at every zoom level.
- Dragging anywhere on the selected image outside an annotation moves the image on the canvas.
- Dragging a corner handle resizes the displayed image while preserving its aspect ratio by default.
- Holding Alt while resizing resizes around the image center.
- Moving or resizing an image carries all of its annotation overlays visually with it.
- Image movement and display resizing must not change annotation source coordinates or crop pixels.
- Arrow keys nudge a selected image by one canvas unit; Shift + Arrow nudges it by ten.
- Duplicate creates a new canvas node pointing to the same local media while copying its current annotations as independent records.
- Bring Forward, Send Backward, Bring to Front, and Send to Back are available through a compact context menu and keyboard shortcuts.

#### Annotation manipulation

- Clicking an annotation selects it instead of selecting its parent image.
- A selected annotation displays edge and corner handles that remain a usable screen size at every zoom level.
- Dragging inside the selected annotation moves the region across the source image.
- Dragging an edge or corner handle resizes the region.
- Annotation movement and resizing are constrained to the source-image bounds; a region cannot extend into empty canvas space.
- A minimum source-region size prevents accidental zero-sized or unusably small crops.
- Arrow keys nudge a selected annotation by one source-image pixel; Shift + Arrow nudges it by ten source-image pixels.
- Double-clicking an annotation, or pressing Enter while it is selected, reopens its fast instruction field.
- Editing the raw instruction reruns semantic interpretation but preserves the annotation ID and region geometry.
- Moving or resizing an annotation preserves its stable asset letter and filename identity, then invalidates and regenerates its derived crop.
- The on-canvas region and lightweight crop preview update during the gesture; the full-quality crop is regenerated after pointer-up or a short debounce.
- Escape cancels an active transform and restores the geometry from before the drag.

#### Deletion and recovery

- Delete or Backspace removes the current selection immediately without a modal dialog.
- Deleting an annotation removes it from the canvas, context set, crop list, manifest, and next export.
- Deleting an image removes its canvas node and attached annotations from the active project view.
- Local source media is retained until project cleanup, allowing immediate Undo and preventing accidental data loss.
- Undo after deleting an annotation restores the same annotation ID, letter, role, instruction, geometry, ordering, and crop filename.
- Undo after deleting an image restores its position, display size, stacking order, annotations, and context inclusion.
- Permanently deleting managed media from the asset library is a separate destructive action and requires confirmation.

#### Undo, redo, and persistence

- Every canvas mutation is undoable: add, paste, move, resize, annotate, edit instruction, include/exclude, reorder, duplicate, group, ungroup, and delete.
- A continuous pointer gesture creates one undo entry when it ends, not one entry per pointer movement.
- Undo and redo update the canvas, inspector, crop list, prompt preview, and validation state together.
- Autosave records the settled state after a gesture without interrupting pointer movement.
- Closing and reopening a project restores image geometry, annotation geometry, stacking order, selection-independent metadata, and current context inclusion.

### 7.5 Context inclusion

Every reference-capable object has one of three states:

- Included in current context.
- Excluded from current context.
- Inherited from its parent group or template.

The app must make inclusion visible without requiring the inspector.

### 7.6 Required end-to-end Phase 1 path

The MVP is incomplete until one project supports this entire sequence without external preparation:

1. Create or reopen a project.
2. Paste or import multiple images.
3. Move and resize the images into a useful board layout.
4. Create multiple annotations per image.
5. Select, move, resize, rename, or delete any annotation after creation.
6. Undo and redo those edits.
7. Enter the creative objective and prompt drafting instructions.
8. Configure and securely store an image-capable drafting-model API key.
9. Preview the exact crops that will be analyzed.
10. Run **Analyze & Draft**.
11. Review and edit the grounded descriptions and detailed filename-linked prompt.
12. Export a flat local folder containing `prompt.md`, `manifest.json`, and every referenced crop.
13. Close and reopen the project without losing the board or draft history.

## 8. Reference roles

MVP presets:

| Role | Typical meaning |
|---|---|
| Character identity | Face, body identity, defining features |
| Face or hair | Face shape, expression, hairstyle, makeup |
| Pose | Body position, gesture, camera-facing angle |
| Wardrobe | Garment, footwear, jewelry, styling |
| Prop | Object held by or placed near a subject |
| Environment | Location, architecture, terrain, background |
| Lighting | Direction, softness, color, contrast, time of day |
| Composition | Framing, camera angle, subject placement |
| Color treatment | Palette, contrast, gradients, glow, and color relationships to preserve |
| Visual style | Medium, texture, rendering or photographic treatment |
| Motion or performance | Body motion, acting, gesture continuity, or choreography from a video |
| Camera movement | Pan, tilt, dolly, orbit, handheld behavior, or stabilization from a video |
| Timing or rhythm | Speed, pacing, pauses, acceleration, cuts, or temporal cadence from a video |
| Negative reference | Elements that must not appear |
| Custom | User-defined semantic role |

Each annotation contains:

- Raw natural-language instruction.
- Drafted role.
- Drafted short label.
- Drafted visual description.
- Drafted what-to-use instruction.
- Drafted what-to-avoid instruction.
- Strength: primary, supporting, or optional.
- Scope: full asset or region.
- Export mode: crop by default, with full asset available only as an explicit override.

The fast path only asks for the raw natural-language instruction. All other values are inferred defaults and remain editable.

### 8.1 Instruction interpretation and description drafting

The description drafter must use both the cropped pixels and the raw instruction. It must not invent a visual description from the instruction alone.

For the instruction `jacket without logo`, the drafter should:

1. Treat `jacket` as the subject to use.
2. Suggest the Wardrobe role.
3. Inspect the crop to describe visible characteristics such as silhouette, material, color, fasteners, and construction when they are actually visible.
4. Treat `without logo` as an exclusion.
5. Produce a concise reference description and prompt-ready use/avoid instructions.

The draft must stay grounded in visible crop content. Uncertain characteristics should be omitted rather than guessed. User edits always take priority over generated wording.

The drafting UI has two levels:

- **Annotation instruction:** the fast, local instruction attached to a crop, such as `jacket without logo`.
- **Prompt drafting instructions:** a persistent multiline field controlling how all annotation descriptions and the final prompt are organized, phrased, and formatted.

The prompt drafting field must be easy to reach without selecting a canvas item and must remember its contents within the project.

### 8.2 Canonical multi-reference example

Objective:

```text
A cute kid dancing in the rain in a neon city.
```

Reference 1 annotation:

```text
Colors and gradients
```

The vision model should identify visible palette and treatment characteristics such as a dark base, saturated violet, electric cyan, hot magenta, luminous gradient transitions, and neon bloom. It must use these characteristics for the new scene while ignoring unrelated typography, layout, and subject matter in the crop.

Reference 2 annotation:

```text
Art style
```

The vision model should identify visible rendering characteristics such as a stylized digital illustration, expressive simplified character shapes, painterly texture, soft dimensional shading, and controlled rim lighting. It must use the rendering language without copying the depicted character's identity, pose, or composition.

An acceptable drafted prompt would contain wording equivalent to:

```text
Create a charming full-body scene of a cute child joyfully dancing in the rain
on a neon-lit city street, with energetic movement, splashing puddles, and a
clear readable silhouette.

COLOR AND GRADIENT REFERENCE — REF_01_A_COLOR_TREATMENT_colors-and-gradients.png
Use the reference only for its color language: a dark navy-to-black foundation,
saturated violet and electric cyan, hot-magenta accents, luminous gradient
transitions, and soft neon bloom. Apply these colors to signs, wet pavement,
reflections, rain, and atmospheric light. Do not copy its typography or layout.

ART-STYLE REFERENCE — REF_02_A_VISUAL_STYLE_art-style.png
Render the scene with the reference's stylized painterly digital-illustration
language: appealing simplified shapes, expressive character features, textured
brushwork, soft dimensional shading, and restrained rim lighting. Do not copy
the reference character's identity, pose, clothing, or composition.
```

The real wording may vary according to the user's prompt drafting instructions, but the semantic assignments and exact filename references must remain explicit.

## 9. Templates and reusable library

### 9.1 Template types

- Character sheet.
- Scene sheet.
- Style board.
- Product shot.
- Fashion editorial.
- Image edit.
- Blank custom template.

### 9.2 Template contents

A template may contain:

- Named empty slots such as Face, Outfit, Pose, and Lighting.
- Default reference roles.
- Default prompt blocks.
- Default positive and negative constraints.
- Default output settings.
- A suggested canvas arrangement.

Template instances should be detachable. Editing a project instance must not silently change the saved template.

### 9.3 Asset library

The local library stores reusable characters, style references, environments, props, and templates. Library records point to locally managed media copies so a project does not break when an original download folder changes.

## 10. Data model

The exact database schema may evolve, but the domain boundaries should remain stable.

```ts
type Id = string;

interface Project {
  id: Id;
  name: string;
  createdAt: string;
  updatedAt: string;
  activeContextSetId: Id;
  canvasState: CanvasState;
  promptDocument: PromptDocument;
}

interface MediaAsset {
  id: Id;
  projectId: Id;
  kind: "image" | "video" | "generated-image";
  originalFilename: string;
  localRelativePath: string;
  contentHash: string;
  mimeType: string;
  width?: number;
  height?: number;
  durationMs?: number;
  frameRate?: number;
  videoCodec?: string;
  audioCodec?: string;
  sourceOrigin: "clipboard" | "local-file" | "remote-url" | "generated";
  sourceUrl?: string;
  playbackProxyRelativePath?: string;
  posterFrameRelativePath?: string;
  importedAt: string;
}

interface VideoImportJob {
  id: Id;
  projectId: Id;
  sourceUrl: string;
  resolvedTitle?: string;
  resolvedDurationMs?: number;
  expectedBytes?: number;
  status: "resolving" | "downloading" | "processing" | "complete" | "failed" | "cancelled";
  progress?: number;
  errorSummary?: string;
  assetId?: Id;
}

interface VideoReferenceAnnotation {
  id: Id;
  assetId: Id;
  scope: "entire-video";
  rawInstruction: string;
  roles: ReferenceRole[];
  draftedDescription: string;
  useInstruction: string;
  avoidInstruction: string;
  draftStatus: "pending" | "drafted" | "edited" | "failed";
  included: boolean;
}

interface ExtractedFrame {
  id: Id;
  sourceVideoAssetId: Id;
  imageAssetId: Id;
  timestampMs: number;
  frameIndex?: number;
  extractionMethod: "playhead" | "uniform" | "scene-change" | "every-frame";
  exportFilename: string;
}

interface CanvasNode {
  id: Id;
  projectId: Id;
  type: "asset" | "note" | "group" | "draft" | "template-instance";
  assetId?: Id;
  parentId?: Id;
  x: number;
  y: number;
  width: number;
  height: number;
  rotation: number;
  zIndex: number;
}

interface Annotation {
  id: Id;
  assetId: Id;
  region?: { x: number; y: number; width: number; height: number };
  rawInstruction: string;
  label: string;
  draftedDescription: string;
  useInstruction: string;
  avoidInstruction: string;
  draftStatus: "pending" | "drafted" | "edited" | "failed";
  strength: "primary" | "supporting" | "optional";
  exportMode: "crop" | "full-asset";
  sequence: number;
}

interface ContextEntry {
  id: Id;
  contextSetId: Id;
  targetType: "asset" | "annotation" | "group";
  targetId: Id;
  included: boolean;
  sequence: number;
}

interface PromptDocument {
  objective: string;
  draftingInstructions: string;
  operation: "analyze" | "generate-image" | "edit-image";
  positiveConstraints: string[];
  negativeConstraints: string[];
  outputSettings: Record<string, unknown>;
  customInstructions: string;
}

interface DraftingProfile {
  id: Id;
  provider: "openai" | "gemini";
  model: string;
  defaultOptions: Record<string, unknown>;
  credentialReference: string;
}

interface DraftRun {
  id: Id;
  projectId: Id;
  draftingProfileSnapshot: DraftingProfile;
  manifestSnapshot: CompiledManifest;
  compiledPrompt: string;
  status: "queued" | "analyzing" | "drafting" | "complete" | "failed" | "cancelled";
  startedAt: string;
  completedAt?: string;
  errorSummary?: string;
}
```

## 11. Reference compiler

The compiler is the central product capability.

### 11.1 Compiler pipeline

1. Resolve the current context set.
2. Expand included groups and template slots.
3. Remove explicit exclusions.
4. Validate annotation regions and local source files.
5. Generate a working crop for each included annotation.
6. Assign one deterministic filename to each included crop before AI analysis so the model sees the same names that will be exported.
7. Send the objective, crops, compact filenames, raw instructions, and prompt drafting instructions to the configured image-capable LLM in one multimodal drafting request. Locally generated labels and roles are not included.
8. Require structured output containing a grounded visual description, use instruction, avoid instruction, confidence/warnings, and contribution-to-final-prompt for every crop.
9. Require the same response to contain a complete detailed final prompt referencing every included crop by its exact filename.
10. Apply any user edits over the drafted values.
11. Validate missing instructions, missing filename references, incomplete drafts, and uncertain interpretations.
12. Preserve the stable reference order and any user-defined ordering.
13. Exclude original source images unless the user explicitly selected full-asset export for a reference.
14. Create the neutral manifest containing the crop descriptions, instructions, and final prompt.
15. Write the local export package.

### 11.2 Deterministic filename format

```text
R{sourceSequence}{regionLetter}.{extension}
```

Example:

```text
R01A.png
R01B.png
R02A.jpg
```

The two-digit sequence identifies the local source asset and the letter identifies the region within it. This compact form minimizes prompt tokens while remaining human-readable. Recompiling unchanged context must produce the same names. The original source filename and local label may remain in the manifest for navigation, but neither is sent to the drafting model.

### 11.3 Manual export structure

```text
ai-canvas-export/
  prompt.md
  manifest.json
  R01A.png
  R01B.png
  R02A.jpg
```

The export is flat by default so the user can select all crop files in one action when uploading them to a chat. It contains generated region crops, not the original pasted images. An original is included only when the user explicitly overrides the crop-only default.

### 11.4 Neutral manifest example

```json
{
  "schemaVersion": 1,
  "operation": "generate-image",
  "objective": "Create a cinematic full-body character portrait.",
  "references": [
    {
      "filename": "R01A.png",
      "sourceAssetId": "asset_01",
      "annotationId": "annotation_01",
      "strength": "primary",
      "rawInstruction": "face and hair, ignore background",
      "description": "The cropped face and hairstyle used as the character identity reference.",
      "use": "Preserve facial identity and hairstyle.",
      "avoid": "Do not copy the background."
    }
  ],
  "positiveConstraints": ["Full-body composition"],
  "negativeConstraints": ["No visible text or logos"],
  "outputSettings": {
    "aspectRatio": "2:3",
    "count": 1
  }
}
```

### 11.5 Compiled prompt structure

The rendered prompt should use stable sections:

```text
OBJECTIVE
[Primary request]

REFERENCE MAP
1. R01A.png
   Instruction: face and hair, ignore background
   Description: The cropped face and hairstyle used as the character identity reference.
   Use: Preserve facial identity and hairstyle.
   Avoid: Do not copy the background.
   Priority: Primary

2. R01B.png
   Instruction: jacket without logo
   Description: A cropped jacket reference from the same source image.
   Use: Use the jacket design shown in this crop.
   Avoid: Do not include or reproduce the logo.
   Priority: Primary

HARD CONSTRAINTS
- Full-body composition.
- Maintain a consistent character identity.

DO NOT INCLUDE
- Visible text or logos.

OUTPUT
- One image.
- Portrait aspect ratio, 2:3.

If references conflict, follow Primary references before Supporting or Optional references.
```

The prompt drafting instructions control the wording and organization of this output. They may request a particular structure, tone, level of detail, syntax, or provider-specific format. Regardless of format, every included crop must be referenced by its exact filename and accompanied by its drafted description and use/avoid meaning.

### 11.6 Multimodal drafting response

The Phase 1 LLM call returns structured data before the UI renders prose. A representative logical schema is:

```ts
interface DraftingResult {
  references: Array<{
    filename: string;
    groundedDescription: string;
    useInstruction: string;
    avoidInstruction: string;
    contributionToPrompt: string;
    confidence: "high" | "medium" | "low";
    warnings: string[];
  }>;
  finalPrompt: string;
  globalWarnings: string[];
}
```

The model must return exactly one record for every included crop. The compiler rejects or repairs drafts that omit a filename, invent a filename, describe unavailable source material, or contradict the crop's raw instruction.

## 12. AI drafting adapter contract

Provider-specific multimodal API details must stay outside the compiler. Phase 1 adapters analyze crops and return text/structured data; they do not request final image generation.

```ts
interface DraftingAdapter {
  id: string;
  capabilities(): DraftingCapabilities;
  validate(input: DraftingInput, profile: DraftingProfile): ValidationIssue[];
  draft(
    input: DraftingInput,
    profile: DraftingProfile,
    signal: AbortSignal
  ): Promise<DraftingResult>;
}
```

Adapters must report capabilities such as:

- Accepted media types.
- Maximum media count or payload size when known.
- Image-understanding support.
- Structured-output or schema support.
- Supported detail/resolution controls.
- Whether reusable remote file references are available.

### 12.1 OpenAI adapter

- Translate the objective, annotation metadata, and crops into multimodal image/text input items.
- Require structured output matching `DraftingResult` when supported.
- Preserve deterministic crop filenames in both the analysis request and returned prompt.
- Return grounded descriptions and prompt text only; do not invoke image generation in Phase 1.

### 12.2 Gemini adapter

- Translate neutral references into Gemini multimodal parts or uploaded file references.
- Require the same provider-neutral `DraftingResult` semantics.
- Support reusable uploaded files where appropriate.
- Return grounded descriptions and prompt text only; do not invoke image generation in Phase 1.

### 12.3 Local export adapter

- Generate a timestamped folder inside the active project's `exports/` directory containing the flat crop set, prompt, and manifest.
- Copy `prompt.md` content to the clipboard.
- Open the export folder after successful creation when the user chooses that option.
- Never claim that files were attached to a third-party chat.

### 12.4 Phase 2 dispatch adapters

Phase 2 may reuse the compiled package to submit the final prompt and crop set to ChatGPT-compatible, OpenAI API, Gemini API, or other destinations. This is a separate boundary from the Phase 1 drafting adapter so analyzing references never accidentally triggers a generation request.

## 13. Validation and warnings

Blocking validation errors:

- No objective.
- Empty context for an operation that requires a reference.
- Missing local source file.
- Invalid or zero-area annotation region.
- No API credential for the selected drafting provider.
- Selected drafting model does not support image input.
- Drafting response omits one or more included crop filenames.

Non-blocking warnings:

- Annotation has no raw instruction or confirmed drafted meaning.
- Drafted description could not be grounded confidently in the crop.
- Multiple Primary references appear to conflict.
- Very small crop may lack useful detail.
- Payload is unusually large.
- Output option will be ignored by the selected provider.
- Negative-reference instructions are ambiguous.

## 14. Local persistence

Recommended project structure:

```text
ProjectName.aicanvas/
  project.sqlite
  media/
  derived/
    thumbnails/
    crops/
  exports/
  logs/
```

Requirements:

- Every project is stored in its own named directory under the user-selected AI Canvas Projects root.
- New directories use the visible project name, with a numeric suffix only when that folder name already exists. Renaming the project also renames its managed directory.
- The project directory contains only that project's document, managed media, and exports; it never contains provider credentials.
- SQLite stores domain records and draft-run metadata.
- Original imports are copied into `media/` using collision-safe names.
- Derived crops and thumbnails are reproducible and may be regenerated.
- Database changes use versioned migrations.
- Autosave occurs after mutations with a short debounce.
- While a named project is active, autosave writes the settled canvas snapshot and newly pasted/imported source media into that project's folder; browser-local IndexedDB remains a fast recovery cache.
- Opening a project tab or choosing a project after **Scan folders** reads its `project.json` and rehydrates managed files from `media/`.
- Application startup scans the managed root and automatically loads the most recently updated project. If none exists, it creates and loads an `Untitled project` folder, preserving any browser recovery snapshot as its initial content.
- Exporting a named project writes a timestamped package beneath that project's `exports/` directory without asking for another destination.
- App-level export settings independently control whether a successful export copies `prompt.md` to the clipboard and opens the timestamped package in File Explorer. These preferences apply across projects.
- A project can be moved as a folder without breaking relative media paths.
- Provider credentials are stored once in a separate local AI Canvas app settings file, not in any project database or folder.

## 15. Local settings and privacy

- Store one API key per configured provider in a single local AI Canvas settings file outside all project folders. This intentionally favors a simple local setup over an OS credential-vault dependency for Phase 1.
- The provider picker automatically loads its supported model list and connection status after the user saves a key.
- Changing providers replaces the model list immediately; model choices are remembered independently per provider and models from another provider never remain visible.
- Never return a saved API key to the renderer; only return whether that provider is configured.
- Do not write full authorization headers to logs.
- Provide Settings fields for provider, model, API key, connection status, key removal, and optional image-detail controls.
- A compact gear button opens a dedicated Settings tab. Provider credentials and connection state are app-level and remain available when switching projects.
- Validate a newly entered credential with a minimal non-image request or provider-supported credential check before saving it.
- Do not upload media during import, thumbnailing, local crop generation, validation, or passive preview.
- Show the exact crops and drafting model before **Analyze & Draft**; this action authorizes uploading those crops for prompt drafting only.
- Do not submit the resulting prompt or crops to a final image generator in Phase 1.
- Provide a setting to delete remotely uploaded drafting files after analysis where supported.
- Make diagnostic logging optional and redact local paths when exporting logs.
- Treat downloaded remote URLs as untrusted input.

## 16. Performance expectations

Initial targets for a typical Windows development machine:

- A warm launch reaches an interactive canvas within 1 second; a cold launch targets 2 seconds.
- Ordinary local interactions acknowledge visually within one animation frame whenever possible.
- Canvas remains interactive with 100 image cards and 200 annotations.
- Pasting a normal image creates a visible card within 500 ms, with heavy work continuing in the background.
- Pan and zoom target a visually smooth 60 FPS under ordinary project load.
- Image and annotation movement/resizing target visually smooth 60 FPS under ordinary project load.
- Full-quality crop encoding is deferred until pointer-up or a short debounce so annotation transforms never wait on image processing.
- The floating annotation instruction field appears and accepts typing within 100 ms after the region drag ends.
- Saving an annotation with Enter does not wait for AI drafting or network access.
- A crop preview updates within 150 ms after the user finishes resizing a region.
- Autosave must not visibly pause canvas interaction.
- Large image decoding and crop generation occur outside the primary UI loop.

These are product targets to validate during the canvas spike, not guaranteed implementation measurements.

## 17. Failure handling

- Every drafting run has an explicit state and remains visible in history.
- Network failures retain the compiled package so drafting can be retried.
- Retry must not duplicate billable requests automatically after an ambiguous timeout.
- Cancellation stops local work and sends provider cancellation only where supported.
- A failed remote upload identifies the affected reference filename.
- Corrupt or unsupported media creates an error card rather than crashing the project.
- Autosave uses transactions so an interrupted write cannot leave a partially updated project.

## 18. Accessibility and usability baseline

- All toolbar actions have labels or tooltips and keyboard-accessible equivalents.
- Role badges use text or icons in addition to color.
- The inspector supports normal keyboard tab order.
- Focus is visibly indicated.
- Default text meets readable contrast requirements.
- Destructive actions are recoverable through undo whenever practical.
- The application supports Windows display scaling at 100%, 125%, 150%, and 200%.

## 19. Analytics for a personal local MVP

No remote analytics are required initially. The app may keep private local counters for product evaluation:

- Time from first import to first compiled package.
- Number of references and annotations per draft.
- Number of compiler warnings.
- Provider success and failure counts.
- Frequency of manual export versus direct dispatch.
- Template reuse count.

Any future remote telemetry must be opt-in and documented.

## 20. MVP acceptance criteria

### Project and media

- A user can create, rename, close, and reopen a project without losing layout or annotations.
- The current project name opens a Figma-style lightweight switcher where `+` creates a project immediately, the name can be edited inline, and another project can be opened in one click.
- Switching projects saves the current project first so rapid navigation cannot silently lose settled work.
- The Projects tab can create, list, explicitly save, and load projects.
- Open projects appear as visible top-left tabs; closing a tab keeps its folder, and selecting it again from the scanned folder list restores the tab and canvas.
- Creating a project creates a distinct folder containing its project document plus dedicated `media/` and `exports/` directories.
- Saving materializes pasted/imported source images into that project's `media/` directory, and loading reconstructs the canvas without relying on the original clipboard or download location.
- Pasted and imported images remain available after the original external file is moved.
- Duplicate file content is detected without incorrectly merging distinct canvas cards.

### Canvas

- A user can pan, zoom, select, move, resize, group, duplicate, delete, undo, and redo.
- Paste, region creation, instruction entry, object movement, and recoverable deletion complete without modal dialogs.
- Both side panels can be collapsed so the canvas becomes the dominant workspace.
- Deleting an object is immediate and recoverable through undo.
- Selecting an image shows persistent screen-sized resize handles, and dragging a corner resizes it proportionally.
- Moving or resizing an image keeps every annotation visually attached while leaving normalized source coordinates and generated crop pixels unchanged.
- A completed move or resize gesture creates exactly one undo entry.
- Image position, display size, and stacking order survive save, close, and reopen.
- A project containing 100 ordinary image cards remains usable under the performance target.
- Canvas transforms never alter stored source-image annotation coordinates.

### Annotation

- A user can create, edit, resize, hide, and delete a rectangular annotation.
- After pressing `R` and drawing a region, the instruction field receives focus automatically without another click.
- Typing `jacket without logo` and pressing Enter saves the region, keeps rapid Region mode active, and makes another region drawable immediately.
- Every annotation stores its authoritative raw instruction, optional local label, visual analysis, geometry, ordering, and export mode.
- The description drafter uses the crop's visible content and the raw instruction rather than relying on the instruction alone.
- Crop output matches the selected source-image region regardless of canvas zoom and card resize.
- Selecting an existing annotation shows move and resize handles without requiring the annotation to be recreated.
- Dragging an annotation changes its normalized source position, keeps it within image bounds, preserves its ID and letter, and regenerates the correct crop.
- Dragging each edge and corner handle changes the corresponding crop boundary and never creates a zero-area region.
- Double-clicking an annotation or pressing Enter reopens its instruction for editing.
- Deleting an annotation removes its crop and filename reference from the preview, manifest, prompt, and export.
- Undo after annotation movement, resizing, instruction editing, or deletion restores the exact previous geometry, metadata, crop, and filename identity.
- Annotation geometry and derived crop identity survive save, close, and reopen.

### End-to-end Phase 1

- A new user can complete paste → arrange → annotate → revise regions → configure drafting API → analyze → edit prompt → export without editing project files manually.
- The project can contain several source images and several independently editable annotations per source image.
- The pre-analysis review displays the same crop pixels and filenames that are sent to the drafting model and written to the export folder.
- Every export can be recreated deterministically after reopening the project.

### Templates

- A user can save a selected arrangement as a reusable template.
- A template can define empty reference slots and default prompt blocks.
- Project instances can be changed without changing the source template.

### Compilation

- Recompiling unchanged context creates identical filenames and reference ordering.
- Generated prompts mention every included crop by its exact generated filename and include its grounded text description.
- Prompt drafting instructions visibly affect the structure and wording of the compiled prompt.
- Excluded assets and annotations do not appear in the manifest, prompt, or outbound file list.
- Manual export contains a readable prompt, valid manifest, and one crop for each included annotation.
- Original pasted images are absent from outbound packages unless the user explicitly enables full-asset export for a particular reference.

### AI drafting

- Provider setup visibly distinguishes not connected, checking, connected, and failed states, and validation errors remain visible beside the API-key field until resolved.
- Selecting Gemini displays only Gemini models; selecting OpenAI displays only OpenAI models. Each provider restores its own last model choice.
- The preview shows the exact drafting provider, model, objective, and crop list before analysis.
- The configured image-capable LLM receives the crops and returns one grounded structured record per crop plus a detailed final prompt.
- `Colors and gradients` affects palette and gradient treatment without importing unrelated layout or text.
- `Art style` affects rendering language without copying subject identity or composition.
- A failed drafting run can be duplicated or retried without rebuilding the project context.
- Unsupported models or media settings are identified before analysis.

### Drafts and export

- Drafted prompt output can be saved as a project revision and edited before export.
- Draft history preserves the crop set, raw annotations, model, structured analysis, manifest, and prompt.
- Export writes a flat local folder containing `prompt.md`, `manifest.json`, and every referenced crop.
- Every exact filename mentioned in `prompt.md` exists in the export folder, and no unmentioned crop is exported.
- The user can independently enable or disable automatic prompt copying and automatic export-folder opening. Manual prompt copy remains available.

### Security

- OpenAI and Gemini can each retain their own key simultaneously in the app settings file.
- Selecting a provider automatically presents its compatible models and configured/unconfigured state.
- API credentials are not stored in project files or ordinary logs.
- No crop upload occurs before **Analyze & Draft**.
- Analyze & Draft cannot trigger final image generation in Phase 1.
- Exporting or sharing a project does not include credentials.

## 21. Delivery milestones

### Milestone 0 — Technical spikes

- Benchmark candidate canvas engines with 100 images and 200 regions.
- Measure launch time, pan/zoom frame rate, paste latency, and region-to-input latency before committing to the canvas stack.
- Prove level-of-detail image rendering so zoomed-out cards use lightweight previews while zoomed-in annotations remain sharp.
- Verify clipboard image paste, native file import, and local media storage.
- Prove source-coordinate annotation and exact crop generation.
- Prove the full no-modal fast path: Ctrl+V, zoom, `R`, drag, type, Enter, then immediately draw the next region.
- Prove one minimal crop-analysis request through the first drafting provider adapter.

Exit condition: The chosen desktop and canvas stack meets the basic workflow and performance targets.

### Milestone 1 — Local canvas

- Project creation and persistence.
- Infinite canvas and image import.
- Image selection, movement, proportional resizing, stacking, duplication, and recoverable deletion.
- Rectangle annotation creation, selection, movement, edge/corner resizing, instruction editing, inclusion, and recoverable deletion.
- Source-coordinate crop regeneration after annotation edits.
- Groups, notes, complete command-based undo/redo, and autosave.

Exit condition: A complete reference board—including edited image geometry, annotation geometry, crop identities, stacking, and context inclusion—survives closing and reopening, and all basic mutations pass undo/redo tests.

### Milestone 2 — AI compiler and local export

- Context sets.
- Prompt document.
- Validation.
- Crop and filename generation.
- Secure API-key settings.
- First image-capable LLM drafting adapter.
- Structured per-crop visual analysis and final prompt generation.
- Manifest, prompt preview, and timestamped flat-folder export within the active project.

Exit condition: The canonical color-treatment plus art-style example produces a grounded detailed prompt and a local folder that can be uploaded manually to an AI chat without renaming or rewriting anything.

### Milestone 3 — Phase 1 refinement

- Second drafting provider adapter.
- Draft history, retry, and cancellation behavior.
- Reference-role conflict warnings.
- Model-quality and latency evaluation using real creative tasks.
- Packaging and Windows installer.

Exit condition: The same context set produces equivalent structured drafts through either drafting provider without project changes.

### Milestone 4 — Phase 2A video ingestion and playback

- Local video import and paste-a-video-link workflow.
- Pluggable URL resolver/downloader with background progress, cancel, retry, and clear unsupported-source errors.
- Project-managed original video, poster frame, metadata, and lightweight playback proxy.
- Movable and resizable video cards with play, pause, seek, mute, and duration controls.

Exit condition: Pasting a supported public video link creates a playable, persistent video card without manual downloading, and reopening the project preserves it.

### Milestone 5 — Phase 2B video references and frame extraction

- Whole-video semantic annotations; no spatial rectangle is required on a video.
- Manual playhead capture, uniform sampling, scene-change keyframes, and guarded every-frame extraction.
- Timestamped deterministic filenames and optional contact sheets.
- Extracted frames become ordinary image assets that support Phase 1 region annotation.
- Direct-video analysis when supported and ordered timestamped-frame fallback otherwise.
- Video-aware prompt compilation and local export.

Exit condition: A user can reference an entire clip for motion, camera behavior, timing, environment, color, or style and can convert it into a controlled frame set for analysis and export.

### Milestone 6 — Phase 2C destination delivery

- Pluggable destination adapters for ChatGPT, Gemini, and future tools through supported APIs, plugins, connectors, or MCP.
- Capability negotiation for prompt, images, video, frame bundles, file count, and file size.
- Final confirmation showing the exact prompt, files, destination, model, and expected cost where available.
- Upload progress, generation state, retry, cancellation, and add-result-to-canvas behavior.
- Manual local export remains available when a direct destination is unavailable.

Exit condition: One click after confirmation submits the same prompt and media package that the user could otherwise upload manually, without relying on brittle website automation.

### Milestone 7 — Reuse and refinement

- Template editor.
- Reusable asset library.
- Faster role assignment and keyboard workflows.
- Comparison of prior runs.

Exit condition: Repeating a familiar workflow is meaningfully faster than manually uploading and describing references.

### Milestone 8 — Phase 3 derived reference maps

- One compact **Generate maps** action on a selected image or extracted video frame.
- Fast local Canny/edge maps with no model download.
- Optional local model installation and execution for depth, pose, line art, normal, and segmentation maps.
- Derived-map persistence, provenance, cache reuse, export, and validation.
- Performance and quality checks on CPU and supported GPU hardware.

Exit condition: A user can select an image, choose one map or a small preset, receive clearly labeled derived reference assets without uploading the source, and include the appropriate maps in a local export.

## 22. Phase 2 — Video references and destination delivery

### 22.1 Video ingestion

Clipboard applications often do not expose copied video bytes reliably. Phase 2 therefore supports three ingestion routes:

1. Drag or import a local video file.
2. Paste a direct public media URL.
3. Paste a supported public video-page URL for a downloader adapter to resolve.

Pasting a recognized HTTP(S) video link creates a video placeholder card immediately. The app resolves title, duration, thumbnail, format, and estimated size, then downloads the media into the project in the background. The card displays resolving, downloading, processing, ready, failed, or cancelled state without blocking the canvas.

Requirements:

- Download progress, transfer speed, cancel, retry, and reveal-source actions.
- Resume partial downloads when the source and downloader support it.
- A user-configurable size threshold; unusually large downloads pause after metadata resolution and request confirmation.
- Collision-safe local filenames, content hashing, and duplicate detection.
- Clear errors for unsupported, expired, private, authenticated, geo-blocked, or DRM-protected sources.
- Downloader adapters may support direct video URLs and selected public services, but must not bypass authentication, DRM, paywalls, or source restrictions.
- Preserve the source URL and retrieval metadata in the project manifest.
- Generate a poster frame and lightweight playback proxy while retaining the best permitted original for export.
- Local file import works even when URL downloading is disabled.

### 22.2 Video card and whole-video annotation

A video card behaves like an image card for canvas layout: it can be selected, moved, resized proportionally, reordered, duplicated, grouped, deleted, undone, and restored after reopening.

The card adds compact playback controls:

- Play and pause.
- Scrubber and current timestamp.
- Duration.
- Mute and volume.
- Playback speed.
- Capture current frame.
- Extract Frames action.

#### Local frame-picker experience

Double-clicking a video card, or choosing **Open frame picker** from its inspector, opens a dedicated local frame picker. This is a reference-selection surface inspired by modern mobile editors such as CapCut and TikTok, not a general-purpose editing timeline.

- Playback, seeking, thumbnails, and frame export operate only from the project-managed local video or its local playback proxy; no new network request is required after import/download.
- The large paused or playing video is the single source of truth for the selected frame. The app must not present a second, conflicting frame preview.
- A thumbnail filmstrip sits under a fixed playhead. Dragging, scrolling, clicking, or keyboard navigation moves the local video to the selected timestamp.
- The picker exposes only the controls needed for reference selection: close, play/pause, timestamp, seamless timeline scaling, and **Export frame** beside the active playhead.
- Left/right arrows step one decoded frame at the current playhead. The exact resolved timestamp is shown to milliseconds and is the timestamp exported.
- Filmstrip navigation uses one continuous timeline rather than named mode tabs. Pinch or Ctrl + wheel scales smoothly from the whole clip to individual-frame precision around the current playhead without losing the selection; ordinary scroll/trackpad movement scrubs.
- When FFmpeg is available, the app creates a project-local, lower-resolution scrub proxy with frequent keyframes in the background. Preview playback, seeking, and thumbnail generation use that optimized proxy; timestamp-accurate frame export always decodes the retained original source.
- Preview thumbnails are generated from the same local source, are low-cost navigation aids rather than exported assets, and are cached by source video plus timestamp. Opening the picker must render the local video immediately; thumbnail work continues progressively without blocking playback or seeking.
- On long clips, the zoomed-out timeline is sampled across the duration and zoomed-in views generate a bounded window around the playhead. The UI must not decode every frame solely to render the first view.
- The user can move rapidly from the beginning to the end of a video, then continuously zoom to individual frames without changing modes or leaving the picker.

Phase 2 annotations apply to the **entire video**, not a spatial rectangle or a time range. A selected video exposes the same fast natural-language instruction field used by images. Examples:

```text
Use the dancing motion and rhythm; ignore the performer and location.
Use the slow orbiting camera movement only.
Use the animation timing, color treatment, and rain behavior.
```

A video may contain more than one whole-video instruction when separate semantic roles are needed. The app converts the instructions into roles such as Motion or performance, Camera movement, Timing or rhythm, Color treatment, Environment, and Visual style.

Activating the Region tool on a video does not create a video rectangle. The UI offers **Capture Frame** or **Extract Frames** when spatial image annotation is required.

### 22.3 Frame extraction and video-to-frames conversion

The Extract Frames action offers:

- **Current frame:** capture the exact playhead position.
- **Keyframes:** select representative frames using scene-change detection.
- **Uniform:** capture one frame every user-defined number of seconds.
- **Target count:** distribute a chosen number of frames across the full duration.
- **Every frame:** advanced mode for short clips, with an explicit storage and frame-count warning.

Before extraction, the app shows estimated frame count and disk usage. The user can choose PNG or JPEG, maximum dimension, JPEG quality, and whether to create individual canvas cards, a contact sheet, or both.

The frame picker is the canonical source for **Current frame** extraction. Exporting from it captures the exact local playhead frame using the selected quality preference; its preview thumbnail is never substituted for the source-resolution export.

Extraction runs in the background with progress and cancellation. Output filenames are deterministic and Windows-safe:

```text
REF_VIDEO_01_FRAME_T000002500.png
REF_VIDEO_01_FRAME_T000005000.png
REF_VIDEO_01_FRAME_T000007500.png
```

The timestamp component is milliseconds from the start of the video. Each extracted frame records its exact timestamp and source-video ID in the manifest.

Extracted frames become standard image assets. They can be moved, resized, region-annotated, renamed, included or excluded, analyzed, and exported using all Phase 1 functionality. Deleting an extracted frame does not modify the original video.

### 22.4 Video analysis strategy

The adapter checks the selected drafting model's declared capabilities before analysis:

- If direct video input is supported, send the managed video with its exact filename and whole-video annotations.
- If direct video input is not supported, create an ordered timestamped frame bundle and send it with a temporal map.
- If motion, camera movement, or timing is requested but the fallback frame density is insufficient, block or warn rather than pretending the temporal analysis is reliable.
- Let the user preview and adjust the sampled frame set before paying for analysis.
- Cache analysis by video hash, annotation text, frame-selection settings, provider, and model.

Phase 2 initially treats video as a visual reference. Audio understanding, transcription, and sound-design references are separate optional capabilities and must not be implied when the chosen model receives no audio.

### 22.5 Video export package

The package contains only the video or derived frames actually referenced by the prompt:

```text
ai-canvas-video-export/
  prompt.md
  manifest.json
  REF_VIDEO_01_MOTION_dance-rhythm.mp4
  REF_VIDEO_02_FRAME_T000004000.png
  REF_VIDEO_02_FRAME_T000008000.png
```

If the target accepts the original video, `prompt.md` references its exact filename and whole-video role. If the target requires frames, the prompt references the ordered frame filenames and timestamps. The manifest records whether the representation is direct video, sampled frames, or both.

### 22.6 Send to ChatGPT, Gemini, or another destination

Destination delivery is adapter-based and remains separate from reference analysis. A destination adapter declares:

- Authentication method.
- Supported prompt and media types.
- Whether it accepts video directly.
- File-count and file-size limits.
- Available models and generation operations.
- Upload, progress, cancellation, result, and error behavior.

Possible implementations include provider APIs, installed ChatGPT plugins/connectors, Gemini APIs, or an MCP server/tool where those surfaces expose the necessary file-transfer and generation capability. The exact route will be chosen later; the project format must not depend on it. Official OpenAI documentation currently describes plugins as a way to extend ChatGPT with skills, MCP servers, and optional UI, but that does not by itself guarantee an arbitrary consumer-chat file-upload workflow.

Before delivery, show one final confirmation containing:

- Destination and account/profile.
- Selected model and operation.
- Exact final prompt.
- Exact video, image, and frame files.
- Capability conversions, such as video-to-frames fallback.
- Known price estimate or a clear statement when unavailable.

Manual export is always available. Do not use browser automation to imitate file uploads unless it is explicitly chosen as a separately maintained experimental adapter.

### 22.7 Phase 2 acceptance criteria

- Pasting a supported public video link creates a downloadable placeholder within 500 ms and a playable local video card after processing.
- Failed, cancelled, and resumed downloads never corrupt the project database or existing media.
- A video card survives move, resize, delete/undo, save, close, and reopen.
- Whole-video annotations can be added, edited, included/excluded, deleted, and restored without spatial regions.
- Current-frame, uniform, target-count, keyframe, and guarded every-frame extraction produce timestamp-accurate files.
- The local frame picker opens without waiting for a full filmstrip, supports overview-to-frame navigation, and exports the exact displayed local frame.
- Extracted frames behave identically to normal Phase 1 images.
- Direct-video and frame-fallback analysis produce manifests that state exactly which representation was analyzed.
- The prompt references every exported video or frame by its exact filename and intended semantic role.
- A destination adapter cannot send unsupported media silently; it must convert with preview or stop with a clear error.
- No prompt or media is delivered externally until the user confirms the final destination package.

## 23. Phase 3 — Local derived reference maps

### 23.1 Purpose and scope

Phase 3 lets a user generate structural reference maps from any local image or extracted video frame in a few clicks. These maps help downstream image-generation tools preserve composition, depth, pose, or edges while the original image remains available as the visual reference.

The feature is a local preprocessing workflow, not an image generator and not an automatic edit to the original asset. It supports:

- **Canny / edges** for high-contrast structure.
- **Depth** for relative scene layout.
- **Pose** for human body, hand, face, and gesture structure where the selected detector supports it.
- **Line art** for simplified contour guidance.
- **Normal** for surface-orientation guidance.
- **Segmentation** for semantic-region reference.

Phase 3 starts with still images and extracted video frames. Whole-video batch processing, masks used to modify original media, and automatic background removal are deferred.

### 23.2 Fast interaction model

Selecting a supported image shows a compact **Generate maps** action in the inspector. It opens a small popover rather than a new workspace or a large settings panel:

```text
Generate maps
  [Edges] [Depth] [Pose]
  More: Line art, Normal, Segmentation
  Presets: Structure (Edges + Depth + Pose) | Illustration (Line art + Normal)
  Generate
```

The user may choose one map or a preset, then presses **Generate** once. Results appear as new, clearly labeled derived image assets beside or stacked with the source. They can be moved, resized, grouped, included/excluded from prompt compilation, annotated, exported, deleted, undone, and restored just like any ordinary image asset.

The original source image is never overwritten, hidden, recolored, or downsampled. The source and every derived map remain visibly linked in the inspector.

### 23.3 Local processing and model policy

- Canny/edge output runs locally with a lightweight image-processing dependency and requires no model download.
- Depth, pose, line art, normal, and segmentation use locally installed open-source preprocessors and their required model weights. A suitable processor bundle may be used behind a provider-neutral local adapter; model-specific code must not leak into project data.
- The app must show the model name, approximate download size, version, license notice/link where required, and storage location before first download. Downloading models requires explicit user confirmation.
- Processing is local. Imported images, extracted frames, generated maps, and model inference results are never uploaded merely to create a map.
- GPU acceleration is used when available and compatible. CPU fallback is allowed, but the UI must report that the task may be slower and remain cancellable.
- Missing, incompatible, or failed models show a clear install/retry/error state without blocking the canvas or disabling maps that are available.

### 23.4 Derived-map data and quality

Each generated map records:

- Source asset ID and source content hash.
- Map type, settings, preprocessor/model name, and model version.
- Source dimensions, generated dimensions, creation time, and local filename.
- Whether the map is stale because its source was replaced.

Maps default to the source image dimensions unless the user explicitly selects a lower working resolution. Map thumbnails may be lightweight, but exported map files retain the selected output dimensions and are never replaced by a thumbnail.

The local cache key is source hash plus map type, settings, and model version. Repeating an identical request reuses the valid output. Cancelling a request removes incomplete temporary output but preserves previously generated maps.

### 23.5 Processing behavior

- Generation runs as a background local job with queued, installing-model, processing, complete, cancelled, and failed states.
- The canvas stays interactive while maps generate; job feedback appears on the source asset and in the status area.
- The first useful result from a multi-map preset appears as soon as it completes. A failed map does not discard successful maps from the same preset.
- Map controls expose only relevant parameters by default: Canny low/high thresholds, optional depth inversion, and pose variant. Advanced preprocessor settings remain collapsed.
- Maps visually distinguish their type through an icon/label, never through ambiguous filenames alone.

### 23.6 Phase 3 acceptance criteria

- Canny output can be generated from a normal local image with one action and no model installation.
- A user can install optional local models only after reviewing the download and storage impact, then create depth and pose maps without uploading the image.
- The **Structure** preset produces independently usable edge, depth, and pose assets; partial success is retained and clearly reported.
- Original and derived maps persist across save, close, reopen, undo/redo, duplication, and local export with their provenance intact.
- Repeating a valid map request uses cached output and does not re-run model inference.
- A long-running model task can be cancelled without corrupting the project or blocking normal canvas interaction.
- Exported maps meet the selected source-quality/output-resolution policy and identify their map type and source in the manifest.

## 24. Post-Phase-3 roadmap

1. Timeline ranges and timestamped subclip annotations.
2. Multiple video tracks or side-by-side motion comparison.
3. Audio transcription and sound-design reference roles.
4. Polygon and brush-mask image annotations.
5. Optional AI-assisted object detection and annotation suggestions.
6. Multiple named context sets per project.
7. Prompt and reference version comparison.
8. Additional provider and destination adapters.
9. Optional encrypted synchronization.
10. Team collaboration and shared libraries if the product expands beyond personal use.

## 25. Decisions intentionally deferred

- Final product name and visual identity.
- Tauri versus Electron, pending the technical spike.
- Exact canvas rendering library, pending performance and licensing review.
- Exact provider/model defaults, because capabilities and pricing change.
- Which public video-page sources the downloader adapter officially supports.
- Which destination uses API, plugin, connector, MCP, or another supported integration surface.
- Whether direct image/video-generation operations ship simultaneously for both initial destinations.
- Whether projects are folders or packaged single-file archives in the final UX.
- Commercial licensing, accounts, billing, and cloud infrastructure.

## 26. Definition of Phase 1 success

The MVP is successful when a user can take a scattered set of visual references, precisely describe which parts matter, compile them into a trustworthy package, and submit that package without manually renaming files or rewriting the reference explanation.

The primary product metric is **time from reference capture to a correctly structured provider request**. The desired improvement should be validated against the user's current manual workflow using several real creative tasks.
