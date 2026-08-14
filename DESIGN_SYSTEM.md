# AI Canvas design system

## Direction

Quiet, precise, and canvas-first: the clarity of Figma/FigJam with the calm surfaces and focused actions of Apple software. The canvas is the product; chrome only appears where it helps the current task.

## Foundations

- **Typeface:** Inter/system UI stack for familiar, highly legible UI text.
- **Accent:** `--blue` is reserved for the primary action, current selection, and active tool.
- **Surfaces:** soft white translucent panels over a near-white dotted canvas.
- **Borders:** low-contrast `--line`; use elevation only for floating or modal surfaces.
- **Corner radius:** `--radius-sm` (8px) for controls and `--radius-md` (12px) for surfaces.
- **Elevation:** `--shadow` for ordinary raised content and `--shadow-float` for controls floating above the canvas.

## Layout rules

- The top bar contains identity, project context, and only two persistent actions: export and analyze.
- The left tool dock floats above the canvas. It is icon-first, collapsible, and reserves its bottom area for Fit and Settings.
- The right inspector is contextual: Prompt, Selection, Projects, and Settings are revealed only when needed.
- Project creation uses the colored plus action. A project name is visible in the header, editable by double-click, and has a close action in the same tab.

## Interaction rules

- Use a primary button only for the next irreversible or main workflow action.
- Keep secondary actions quiet until hover, selection, or a contextual panel makes them relevant.
- Never use color as the only state indicator; pair it with label, icon, or position.
- Preserve keyboard shortcuts and tooltip text for every icon-only action.
- Keep destructive actions visually quiet until invoked, then ask for confirmation where appropriate.

## Logo placeholder

The header uses a small vector `A`-shaped mark in `.brand-mark`. It is intentionally self-contained in `prototype/index.html` so it can be replaced with an approved SVG or brand asset later without changing layout or behavior.
