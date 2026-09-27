# Third-party components

AI Canvas source is Apache-2.0. The dependencies below are obtained from their upstream package registries or repositories and retain their own licenses. This repo does not include model weight files or copies of ComfyUI.

| Component | Use | Upstream/license information |
| --- | --- | --- |
| [OpenCV](https://github.com/opencv/opencv) | Canny and image processing | Upstream license applies |
| [Pillow](https://github.com/python-pillow/Pillow), [NumPy](https://github.com/numpy/numpy) | Image processing | Upstream licenses apply |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Optional public video-page downloads | Upstream license applies |
| [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg) | Local FFmpeg binary | Check both wrapper and bundled FFmpeg build notices upstream |
| [PyTorch](https://github.com/pytorch/pytorch), [Transformers](https://github.com/huggingface/transformers) | Optional learned maps | Upstream licenses apply |
| [controlnet-aux](https://github.com/huggingface/controlnet_aux) | Optional pose, line, HED, and normal processors | Apache-2.0 for the package source; weights are separate |
| [Depth Anything V2 Small](https://huggingface.co/depth-anything/Depth-Anything-V2-Small-hf) | Optional depth weights | Model card declares Apache-2.0. Larger V2 variants have different terms and are not bundled. |
| [lllyasviel/Annotators](https://huggingface.co/lllyasviel/Annotators) | Optional pose, line, HED, and normal weights | Model card currently says `license: other`; review individual weight terms before redistribution. AI Canvas downloads weights from upstream on demand and does not redistribute them. |
| [ComfyUI](https://github.com/comfyanonymous/ComfyUI) | Optional user-run custom map engine | Separate installation and its own license; workflows and custom model weights may have additional terms |

This list is a release checklist, not a substitute for the upstream license files. Before producing a bundled installer, record exact dependency versions, model revisions, downloaded artifacts, and the notices required by each included binary.
