# Animation manifest

Use a manifest when frame durations differ or the frame order should not depend
on filenames.

```json
{
  "schema": "image-enhance/gif-animation/v1",
  "loop": 0,
  "frames": [
    {"path": "frames/frame_01.png", "durationMs": 300},
    {"path": "frames/frame_02.png", "durationMs": 300},
    {"path": "frames/frame_03.png", "durationMs": 700}
  ]
}
```

- Resolve relative frame paths from the manifest directory.
- Set `loop` to `0` for infinite playback or a positive repeat count.
- Specify every `durationMs` as an integer from 1 to 60000. GIF storage rounds
  durations to 10 ms increments.
- Keep frame count at or below 500 and decoded pixels at or below 100 million.
