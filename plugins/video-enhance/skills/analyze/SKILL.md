---
name: analyze
description: Inspect and analyze local video files through Video Enhance, including summaries, precise timelines, screen OCR, and visual questions.
---

# Analyze video

Use this workflow when `$video-enhance:analyze` is invoked or a local video needs inspection or provider-backed visual analysis.

Call `video_config_status` before provider-backed analysis. Never ask the user to put an API key in a tool argument, prompt, or chat message; direct them to the local config file reported by that tool. Check `delete_remote_files` and accurately explain the configured retention policy before uploading. If it is `false`, state that the provider upload will intentionally remain remote; if it is unknown, resolve the configuration error before analysis.

Call `video_inspect` before analysis to verify the local path, duration, dimensions, container, audio presence, and access policy without uploading anything.

Then call `video_analyze`:

- Use `profile="balanced"` for summaries and ordinary visual questions.
- Use `profile="temporal"` for precise event timelines or fast UI activity.
- Use `profile="ocr"` when small on-screen text is central.
- Leave `provider="auto"` unless the user explicitly requests a configured provider.

Explain before analysis that the tool creates an audio-free visual proxy and uploads it to the selected provider. Call it temporary only when `delete_remote_files` is `true`. Do not claim the analysis heard speech or other audio.

Treat `status="partial"`, invalid timestamp coverage, cleanup or retention warnings, and uncertainties as real limitations. Surface them rather than presenting the result as fully verified.
