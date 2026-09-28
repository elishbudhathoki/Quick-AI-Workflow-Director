# AI Canvas

AI Canvas is a local-first visual workspace for collecting image and video references, annotating them, drafting prompts, extracting video frames, and exporting reference maps. It runs as a local server in your browser. No account is required. OpenAI or Gemini drafting is optional and uses your own API key.

## Desktop source install

Supported first-release targets: Windows, macOS, and Linux desktops with Python **3.11–3.13** (3.12 recommended), Git, a modern browser, and an internet connection for initial dependency downloads. Install [Python 3.12 from its official downloads page](https://www.python.org/downloads/) if the `python` command is missing; on Windows, enable its PATH option during installation. The app runs on CPU; learned maps are faster with a compatible GPU. Mobile devices are not a supported target.

```sh
git clone https://github.com/elishbudhathoki/Quick-AI-Workflow-Director.git
cd Quick-AI-Workflow-Director
python setup.py
python start.py
```

On Windows, use `py -3 setup.py` and `py -3 start.py` if the Python launcher is available instead of `python`. If this checkout already has a `.venv`, `.\.venv\Scripts\python.exe setup.py` works without a system-wide Python command. On macOS/Linux, `python3` may be the command instead of `python`. Setup creates a private `.venv` in the checkout and installs the core image, video, and Canny dependencies. Start opens <http://127.0.0.1:4173/> in your default browser. Leave the terminal open; press Ctrl+C to stop. If the browser does not open automatically, visit that address yourself. Use `python start.py --port 4174` if the default port is occupied.

To add **Depth, Human pose, Outline, Soft edge, Normal, and Scribble** maps:

```sh
python setup.py --maps
```

This optional step installs PyTorch and model-processing packages and may use substantial disk space. Published model weights download from their upstream repositories when a learned map is first generated; no weights are included in this repo. Canny needs no model download. Animal pose and custom map models use a separately installed local ComfyUI workflow. See [model sources and licenses](THIRD_PARTY_NOTICES.md) before distributing any weights.

The app uses an FFmpeg binary from `imageio-ffmpeg` for video processing. Some public video sites can still impose their own restrictions. Provider drafting supports Gemini, OpenAI, Groq, OpenRouter, Anthropic, xAI, and Mistral. Choose **Custom API** for an OpenAI-compatible vision endpoint and enter its base URL, model ID, and key. Custom endpoints require HTTPS unless they run on this device. OpenRouter also gives access to many other vision models through one key. Map generation itself is local.

## Where files go

| Data | Windows | macOS | Linux |
| --- | --- | --- | --- |
| Projects and exports | `~/Documents/AI Canvas Projects` | `~/Documents/AI Canvas Projects` when Documents exists; otherwise app data `projects/` | Same as macOS |
| App preferences | `%LOCALAPPDATA%/AI Canvas/settings.json` | `~/Library/Application Support/AI Canvas/settings.json` | `${XDG_DATA_HOME:-~/.local/share}/ai-canvas/settings.json` |
| API keys | Windows Credential Manager | macOS Keychain | Secret Service compatible desktop keyring |
| Learned model weights | Hugging Face and processor caches for the current user | Same | Same |

Provider API keys remain on your device in its credential store and reconnect when AI Canvas starts. Existing keys in `settings.json` are migrated and removed from that file when the credential store is available. On Linux, persistent keys require an unlocked Secret Service compatible keyring; without one, use an environment variable such as `GEMINI_API_KEY`. The app never copies projects or keys into the source checkout. Use `python start.py --projects-dir PATH --settings-file PATH` to choose other data locations, or set `AI_CANVAS_PROJECTS_DIR` for the project root. See [storage details](docs/STORAGE.md).

## Updating this clone

Stop the server, save your changes to the source code if you made any, then run:

```sh
git pull
python setup.py
python start.py
```

If you use learned maps, rerun `python setup.py --maps` after updates to their dependencies. Project and settings folders are outside the checkout and are not removed by updating it. Back up your projects before moving between major releases. Contributors should read [CONTRIBUTING.md](CONTRIBUTING.md).

## Status and scope

This is a desktop **source release**, not a packaged installer. The local server defaults to `127.0.0.1`; do not expose it on a public network. Browser editing and local project saves work without an AI provider. Model downloads, public video imports, and optional provider drafting require network access. The [prototype guide](prototype/README.md) covers the current interface and workflows. [Known and deferred work](TODO.md) is tracked separately.

Licensed under [Apache-2.0](LICENSE). Third-party libraries and model weights retain their own licenses; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
