# Ordered Segment Stitching

Use this runbook only when one final deliverable contains multiple newly
generated Flow segments. All segments belong to the same dedicated leaf worker.

## Generate and retain ordered segments

1. Give every segment a stable ordered ID such as `<item-id>-s01`.
2. Generate, download, and verify one segment completely before submitting the
   next. Every Flow submission remains `x1`.
3. Maintain continuity in segment prompts when requested, but never invent a
   visual reference upload. Use only explicitly authorized images.
4. Apply the live quote gate independently to every attempt. Subtract each
   submitted quote from the worker's remaining item and invocation budgets
   before the next segment.
5. Allow at most two attempts per segment under the provider failure rules.
6. Keep verified segments in `OUTPUT_DIRECTORY/segments/` with collision-free
   names. Do not delete them after stitching.

If any segment is failed, paused, or pending, do not stitch a partial final
video unless the user explicitly revises the requested deliverable.

## Chain visual continuity

Default stitched narratives to `continuity=frame-chain`. After verifying
segment N, extract its final decoded frame before configuring segment N+1:

```text
uv run --locked --project <video-enhance-plugin-root> python \
  <create-skill-root>/scripts/extract_boundary_frame.py \
  --input <segment-N.mp4> \
  --output <collision-free-continuity/segment-N-last.png> \
  --position last
```

The derived PNG is authorized only as the next segment's `start_frame`. Keep it
under OUTPUT_DIRECTORY, record it in the segment result, and never upload it
elsewhere. Configure segment N+1 in frame mode with that exact PNG. This does
not mix ingredient and frame modes: ingredients may establish segment 1, while
later segments use the preceding generated frame.

Write each continuation prompt as a continuation, not a fresh scene. Preserve
from the prior segment:

- character identity, clothing, props, spatial relationships, and background;
- camera position, lens feel, framing, motion direction, and motion speed;
- subject pose, velocity, gaze, lighting, weather, and time of day.

State the new action that should happen after the supplied first frame. Avoid
language that re-establishes or resets the scene. If the requested model,
duration, ratio, or frame mode is unavailable, return the currently visible
alternatives and do not silently fall back to prompt-only continuity.

Use `continuity=explicit` when the user supplies a start frame for every
segment. Use `continuity=independent` only when the user explicitly wants
separate shots. Explicit per-segment frames take precedence over derived
frames.

After downloading segment N+1, use the same helper with `--position first`.
Directly compare the two boundary images when visual inspection is available.
Report an observable identity, composition, or motion discontinuity as a
warning. Do not spend credits on an automatic retry because seam quality is
subjective unless a machine-verifiable specification also failed.

## Assemble locally

The bundled helper performs hard-cut concatenation and consumes no Flow
credits:

```text
uv run --locked --project <video-enhance-plugin-root> python \
  <create-skill-root>/scripts/stitch_videos.py \
  --output <collision-free-final.mp4> \
  <ordered-segment-01.mp4> <ordered-segment-02.mp4> [...]
```

Locate the plugin and skill roots from the current skill path; never assume a
fixed installation directory. Pass segments in the exact requested order.
Never use a shell glob to establish order.

The helper:

- refuses fewer than two inputs and refuses to overwrite an output;
- first attempts verified stream-copy for compatible inputs;
- falls back to a high-quality local H.264/AAC normalization when stream-copy
  fails or produces the wrong total duration;
- preserves the first segment's dimensions and frame rate during fallback,
  scaling and padding later segments without cropping;
- synthesizes silence only for a segment that has no audio;
- verifies final duration against the sum of segment durations;
- emits one JSON result with `stream-copy` or `normalized-transcode`.

Treat a nonzero exit, malformed JSON, missing output, or duration mismatch as
`failed`; local stitching is not a provider retry and never authorizes another
generation attempt.

## Verify and report

Run `video_inspect` on the assembled MP4 using the final-path or same-inode
allowed-root procedure from the main worker contract. Confirm:

- duration approximately equals the sum of verified segments;
- dimensions and container are valid;
- byte size is nonzero;
- segment order in the returned metadata matches the requested order.

Return every segment's ID, local path, attempts, live quotes, and final prompt.
Also return every derived continuity frame and the continuity mode. Set
`stitch_strategy` from the helper JSON. The final deliverable's estimated
credit spend is the sum of all submitted segment attempts; frame extraction
and stitching add zero.
