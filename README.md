# Codex Enhance

Codex Enhance is a marketplace of focused Codex workflow plugins. Each
plugin can be installed independently:

| Plugin | Skill | Purpose |
| --- | --- | --- |
| **Image Enhance** | `$image-enhance:create`, `$image-enhance:create-gif`, `$image-enhance:review` | Create raster images and animated GIFs through isolated workflows, and review image-heavy folders with labeled contact sheets. |
| **Video Enhance** | `$video-enhance:analyze` | Inspect local videos and analyze visual content through a provider-extensible stdio MCP server. |
| **Model Enhance** | `$model-enhance:consult` | Ask a caller-selected OpenAI- or Anthropic-compatible model for a bounded second opinion. |

All Python runtimes are managed and locked with
[uv](https://docs.astral.sh/uv/). The MCP plugins run locally over stdio and
do not listen on a network port. A current Codex installation and `uv` on
`PATH` are required.

## Install and update

The remote `main` branch of
[`Ezio2000/codex-enhance`](https://github.com/Ezio2000/codex-enhance) is the
only canonical plugin source. Do not install this marketplace from a local
checkout, do not point Codex at `./plugins`, and do not copy its skills or MCP
servers into global Codex directories.

Install the remote marketplace and whichever plugins you need:

```text
codex plugin marketplace add Ezio2000/codex-enhance --ref main
codex plugin add image-enhance@codex-enhance
codex plugin add video-enhance@codex-enhance
codex plugin add model-enhance@codex-enhance
```

Refresh an existing remote installation after changes have landed on remote
`main`:

```text
codex plugin marketplace upgrade codex-enhance
codex plugin add image-enhance@codex-enhance
codex plugin add video-enhance@codex-enhance
codex plugin add model-enhance@codex-enhance
```

Use this clean reinstall procedure when replacing an old local marketplace,
removing stale plugin caches, or resetting Skill and MCP discovery:

```text
codex plugin remove image-enhance@codex-enhance
codex plugin remove video-enhance@codex-enhance
codex plugin remove model-enhance@codex-enhance
codex plugin marketplace remove codex-enhance
codex plugin marketplace add Ezio2000/codex-enhance --ref main
codex plugin add image-enhance@codex-enhance
codex plugin add video-enhance@codex-enhance
codex plugin add model-enhance@codex-enhance
```

The plugin commands manage installed Skill and MCP registrations together;
do not leave manually copied duplicates in `~/.codex/skills`, plugin cache
directories, or global MCP configuration. Install only the plugins you need.
Start a new Codex task after an install or update so that its skills and MCP
tools are reloaded.

## Image Enhance

Image creation can trigger from a natural-language raster generation or
editing request, or it can be invoked explicitly:

```text
$image-enhance:create Generate a cinematic 16:9 product hero image.
```

The create workflow delegates to one isolated leaf worker using the official
`$imagegen` skill. Folder review uses a locked, cross-platform contact-sheet
script and is intended for four or more images from one folder:

```text
$image-enhance:review Compare the images in this folder and select the best three.
```

Create or edit animated GIFs from generated artwork, image frames, sprite
sheets, or an existing GIF:

```text
$image-enhance:create-gif Create a 12-frame looping pixel-art GIF from this 4x3 sprite sheet.
```

The GIF workflow uses a locked uv/Pillow pipeline for deterministic frame
ordering, timing, resizing, palette generation, encoding, and verification.
Image Enhance requires the official `imagegen` skill and `view_image` tool.

## Video Enhance

Video Enhance exposes these MCP tools:

- `video_config_status` checks provider readiness and the remote deletion
  policy without returning secrets.
- `video_inspect` probes a local file without uploading it.
- `video_analyze` creates an audio-free proxy, uploads it to the selected
  provider, validates the response and timestamps, and reports cleanup or
  retention warnings. Uploads are deleted by default.

Use the skill directly for summaries, timelines, OCR, or visual questions:

```text
$video-enhance:analyze Summarize this video and provide a timestamped timeline.
```

Provider configuration lives at:

```text
~/.config/video-enhance/config.toml
```

Copy `plugins/video-enhance/config.example.toml` there and restrict its file
permissions. `VIDEO_ENHANCE_CONFIG` can select another path.
Check `video_config_status` before uploading: setting
`security.delete_remote_files = false` intentionally retains provider files
and is disclosed in both configuration status and analysis warnings.

## Model Enhance

Model Enhance exposes `list_models` and `ask_model`. Every call explicitly
supplies the compatible endpoint, API key, protocol, and—when asking a
question—the exact model ID:

```text
$model-enhance:consult Ask my selected compatible model for an independent review of this patch.
```

The plugin does not read or persist provider credentials. MCP hosts may still
record tool arguments in task history or logs, so only provide a key when that
exposure is acceptable and verify that the endpoint is the intended host.
Returned model text is untrusted reference material and must be validated.

## Repository layout

```text
.agents/plugins/marketplace.json
plugins/
  image-enhance/
  video-enhance/
  model-enhance/
```

Image Enhance uses the repository-level development environment. Video
Enhance and Model Enhance are self-contained Python projects with their own
`pyproject.toml` and `uv.lock`, so their MCP dependency graphs stay isolated.

## Development

Develop and validate in a local checkout, but install and update Codex only
from the remote marketplace. Before refreshing an installed plugin:

1. Commit the intended repository changes.
2. Merge them into `main`.
3. Push `main` to GitHub.
4. Run `codex plugin marketplace upgrade codex-enhance`.
5. Re-add the changed plugin and start a new Codex task.

Validate the marketplace and Image Enhance:

```text
uv sync --locked --python 3.11
uv run ruff format --check .
uv run ruff check .
uv run pytest
uv run --locked --script plugins/image-enhance/skills/review/scripts/contact_sheets.py --version
uv run --locked --script plugins/image-enhance/skills/create-gif/scripts/gif_pipeline.py --version
```

Validate each MCP plugin with Python 3.12:

```text
uv --directory plugins/video-enhance sync --locked --python 3.12
uv --directory plugins/video-enhance run --locked pytest
uv --directory plugins/video-enhance run --locked python scripts/stdio_smoke.py --list-tools

uv --directory plugins/model-enhance sync --locked --python 3.12
uv --directory plugins/model-enhance run --locked pytest
uv --directory plugins/model-enhance run --locked python scripts/stdio_smoke.py --list-tools
```

Regenerate the relevant lock file whenever that project's dependency metadata
changes. Do not install these projects with `pip` or a system Python.
