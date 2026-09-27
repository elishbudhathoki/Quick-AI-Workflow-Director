# Contributing

AI Canvas is currently a small local-first desktop source project. See [README.md](README.md) for setup. For a fast local check, run:

```sh
python -m unittest discover -s tests
python -m py_compile prototype/server.py prototype/map_processor.py prototype/comfy_maps.py
```

Run `python start.py --mock-ai` to exercise drafting without a provider key. Keep personal projects, exported media, API keys, downloaded weights, and `.venv` out of commits. Add a small test for changes that affect saved data, request validation, or map/video processing. Describe platform-specific behavior in a pull request and check it on a clean clone where possible.

The project license is Apache-2.0. Only submit code and assets that you have permission to contribute under that license; model weights and downloaded user media should remain upstream or local.
