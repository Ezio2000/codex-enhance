# Codex Enhance

Codex Enhance is a Codex plugin marketplace for focused workflow
enhancements. Its first plugin, Image Enhance, contains two skills:

- `$image-enhance:create` delegates raster generation or editing to one
  isolated leaf worker that uses the official `$imagegen` skill.
- `$image-enhance:review` efficiently reviews four or more images from one
  folder through labeled, cross-platform contact sheets.

The review runtime uses a locked PEP 723 Python script through
[uv](https://docs.astral.sh/uv/). It does not require PowerShell,
ImageMagick, a system Python installation, or platform-specific fonts.

Requirements are a current Codex installation with the official `imagegen`
skill and `view_image` tool, plus `uv` available on `PATH`.

## Install

From a local checkout:

```text
codex plugin marketplace add /absolute/path/to/codex-enhance
codex plugin add image-enhance@codex-enhance
```

After publishing this repository on GitHub:

```text
codex plugin marketplace add Ezio2000/codex-enhance --ref main
codex plugin add image-enhance@codex-enhance
```

Start a new Codex thread after installation or upgrade so the new skills are
loaded.

## Usage

Creation can trigger from a natural-language raster generation or editing
request, or it can be invoked explicitly:

```text
$image-enhance:create Generate a cinematic 16:9 product hero image.
```

The create workflow uses `fork_turns: "none"`, an implicit-invocation policy,
and a leaf-worker prompt to prevent recursive delegation. These are workflow
guardrails, not an operating-system-level tool sandbox.

Folder review can trigger from its skill description. For deterministic
routing by image count, add this rule to your global or repository
`AGENTS.md`:

```text
Analyze one to three images with direct visual reads. When reading, comparing,
selecting, classifying, or summarizing four or more images from the same
folder, use $image-enhance:review.
```

## Development

The installable plugin is under `plugins/image-enhance`; repository-level
development dependencies, tests, and `uv.lock` stay outside that directory.
The marketplace entry is under `.agents/plugins/marketplace.json`.

```text
uv sync --locked
uv run ruff check .
uv run pytest
uv lock --script plugins/image-enhance/skills/review/scripts/contact_sheets.py
```

The repository `uv.lock` is committed for reproducible development and CI but
is not part of the installable plugin directory. The adjacent script lock must
be regenerated whenever the runtime script's inline dependency metadata
changes.

## Add another plugin

Add each future plugin under `plugins/<plugin-name>` with its own
`.codex-plugin/plugin.json`, then append a matching entry to
`.agents/plugins/marketplace.json`. Keep the plugin folder, manifest `name`,
and marketplace entry `name` identical.

Users can then install any plugin from this marketplace with:

```text
codex plugin add <plugin-name>@codex-enhance
```
