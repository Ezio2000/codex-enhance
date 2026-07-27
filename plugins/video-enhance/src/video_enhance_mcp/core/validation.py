"""Provider-response parsing and timeline coverage validation."""

from __future__ import annotations

import json

from json_repair import repair_json

from .schemas import AnalysisPayload, Coverage


def _strip_json_wrapper(content: str) -> str:
    value = content.strip()
    if value.startswith("```json") and value.endswith("```"):
        return value[7:-3].strip()
    if value.startswith("```") and value.endswith("```"):
        return value[3:-3].strip()
    return value


def _truncate(value: object, warnings: list[str]) -> object:
    if not isinstance(value, dict):
        return value
    result = dict(value)
    for field, limit in {"summary": 2000, "answer": 6000}.items():
        item = result.get(field)
        if isinstance(item, str) and len(item) > limit:
            result[field] = item[:limit]
            warnings.append(
                f"provider field {field} was truncated to {limit} characters"
            )
    for field, limit in {
        "timeline": 20,
        "observations": 30,
        "uncertainties": 20,
    }.items():
        item = result.get(field)
        if isinstance(item, list) and len(item) > limit:
            result[field] = item[:limit]
            warnings.append(f"provider field {field} was truncated to {limit} items")
    timeline = result.get("timeline")
    if isinstance(timeline, list):
        for index, event in enumerate(timeline):
            if not isinstance(event, dict):
                continue
            if (
                isinstance(event.get("description"), str)
                and len(event["description"]) > 500
            ):
                event["description"] = event["description"][:500]
                warnings.append(f"timeline event {index} description was truncated")
            screen_text = event.get("screen_text")
            if isinstance(screen_text, list):
                if len(screen_text) > 10:
                    warnings.append(
                        f"timeline event {index} screen_text was truncated to 10 items"
                    )
                event["screen_text"] = [
                    text[:120] if isinstance(text, str) else text
                    for text in screen_text[:10]
                ]
    for field in ("observations", "uncertainties"):
        if isinstance(result.get(field), list):
            result[field] = [
                text[:500] if isinstance(text, str) else text for text in result[field]
            ]
    return result


def parse_analysis_payload(
    content: str, warnings: list[str] | None = None
) -> AnalysisPayload:
    parse_warnings = warnings if warnings is not None else []
    value = _strip_json_wrapper(content)
    if not value.startswith("{"):
        raise ValueError("response does not start with a JSON object")
    if not value.endswith("}"):
        raise ValueError("response contains text after the JSON object")
    decoder = json.JSONDecoder()
    try:
        parsed, end = decoder.raw_decode(value)
        if value[end:].strip():
            raise ValueError("response contains text after the JSON object")
    except json.JSONDecodeError:
        parsed = repair_json(value, return_objects=True)
        parse_warnings.append(
            "provider JSON syntax was repaired locally before validation"
        )
    return AnalysisPayload.model_validate(_truncate(parsed, parse_warnings))


def validate_coverage(
    analysis: AnalysisPayload,
    duration_ms: int | None,
    *,
    require_full_coverage: bool,
) -> tuple[Coverage, list[str]]:
    warnings: list[str] = []
    valid = True
    previous_start = -1
    for index, event in enumerate(analysis.timeline):
        if event.start_ms < previous_start:
            warnings.append(f"timeline event {index} is out of order")
            valid = False
        previous_start = event.start_ms
        if duration_ms is not None and event.end_ms > duration_ms + 250:
            warnings.append(f"timeline event {index} exceeds the source duration")
            valid = False
    timeline_end = max((event.end_ms for event in analysis.timeline), default=None)
    if require_full_coverage:
        if not analysis.timeline:
            warnings.append("a full-video operation returned no timeline")
            valid = False
        elif duration_ms is not None:
            tolerance = max(1000, round(duration_ms * 0.15))
            if analysis.timeline[0].start_ms > tolerance:
                warnings.append(
                    "timeline does not start near the beginning of the video"
                )
                valid = False
            if timeline_end is None or timeline_end < duration_ms - tolerance:
                warnings.append("timeline does not cover the end of the video")
                valid = False
    return Coverage(
        duration_ms=duration_ms, timestamp_valid=valid, timeline_end_ms=timeline_end
    ), warnings
