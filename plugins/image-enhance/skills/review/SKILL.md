---
name: review
description: Inspect, compare, select, classify, or summarize four or more local images from the same folder by building temporary labeled contact sheets with the bundled cross-platform uv/Python tool, reading the sheets with view_image, and retaining an ID-to-source manifest. Use automatically for folders containing at least four relevant JPEG, PNG, WebP, BMP, GIF, TIFF, HEIC, HEIF, or AVIF images, including folders mixed with non-images or corrupt files. For one to three images, use direct visual reads instead. Do not use for image generation, editing, or exact pixel-forensic inspection.
---

# Review Image Folders

Build normalized contact sheets before calling `view_image`. Keep the manifest
that maps each visible `IMG_00001` label to its original source path, then
remove the generated review directory in a `finally`-style cleanup step.

## Route by image count

- For one to three images, read the original images directly and do not run
  this workflow.
- For four or more images from the same folder, use this workflow.
- Scan only the selected directory unless the user explicitly requests
  recursion.
- Read an original image separately only when a necessary detail is not
  legible on its contact sheet.

## Resolve the bundled paths

Let `<skill-directory>` be the directory containing this `SKILL.md`. The
script is:

```text
<skill-directory>/scripts/contact_sheets.py
```

The script declares and locks its own Python dependencies. Run it only with
`uv`; do not call a system Python, PowerShell, or ImageMagick.

## Build contact sheets

Run the same command on Windows, Linux, and macOS:

```text
uv run --locked --script "<skill-directory>/scripts/contact_sheets.py" build --source "<folder>"
```

Add `--recursive` only when requested. Use `--grid-size 2` when larger visual
detail matters, `3` for the default balance, or `4` for high-throughput
screening.

The command writes one JSON object to stdout. Read its `manifestPath`, then:

1. Read `manifest.json`.
2. Inspect every path in `sheets`, ordered by `index`.
3. Call `view_image` sequentially with one sheet per call and
   `detail: "high"`.
4. Refer to visible image IDs in the analysis and map them back through
   `images[].sourcePath`.
5. Report skipped corrupt candidates from `invalidImages` when relevant.

An empty `sheets` array is a successful scan with no decodable candidates;
use `invalidImages` and the file counts to explain why.

## Preserve review quality

- Treat extensions case-insensitively.
- Decode only the first frame or page of multi-frame formats.
- Preserve source files unchanged.
- Use the manifest rather than guessing filenames from thumbnails.
- Keep visual calls sequential to bound peak memory.
- Do not print Base64 or data URLs.
- Do not add OCR, hashing, caching, or semantic preprocessing unless the user
  explicitly asks for it.

## Always clean up

After all required visual reads, or after any failure following a successful
build, run:

```text
uv run --locked --script "<skill-directory>/scripts/contact_sheets.py" cleanup --manifest "<manifestPath>"
```

The cleanup command validates both the manifest and an ownership marker before
removing the generated directory. Never delete the directory manually and
never pass a source-image path to cleanup.
