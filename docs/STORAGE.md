# Storage and updates

AI Canvas separates source code from user data. The `.venv` virtual environment is local to a clone and can be rebuilt with `python setup.py`. Projects, exports, and provider settings live outside the clone by default.

- Each project has a `project.json`, `media/`, and `exports/` directory. `project.json` currently uses `schemaVersion: 1`. Keep the whole project folder together when backing up or moving it.
- Windows retains the existing `~/Documents/AI Canvas Projects` root and `%LOCALAPPDATA%/AI Canvas/settings.json`. The desktop source release does not relocate existing projects or keys.
- On macOS and Linux, projects go to `~/Documents/AI Canvas Projects` when Documents exists, otherwise to the OS app-data directory under `projects/`. Settings use `~/Library/Application Support/AI Canvas` on macOS and `${XDG_DATA_HOME:-~/.local/share}/ai-canvas` on Linux.
- `AI_CANVAS_PROJECTS_DIR` or `start.py --projects-dir` selects a different project root. `start.py --settings-file` selects a different settings file.
- Hugging Face downloads use its normal cache location. Set `HF_HOME` before starting AI Canvas to choose another location. ControlNet Aux may use its own cache; see that project's documentation for `AUX_ANNOTATOR_CKPTS_PATH`. Do not store downloaded weights inside Git.

Updating the source checkout does not delete user data. Back up project folders before manually changing project JSON or upgrading across a future schema change. Automated schema migration and rollback are still planned; there is no migration to apply for the current `schemaVersion: 1` format.
