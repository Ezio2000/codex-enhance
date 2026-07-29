import json

import pytest

from video_enhance_mcp.core.validation import parse_analysis_payload, validate_coverage
from video_enhance_mcp.server import mcp


def _payload(*, end_ms: int = 10_000) -> dict[str, object]:
    return {
        "summary": "测试视频",
        "answer": "完成",
        "timeline": [
            {
                "start_ms": 0,
                "end_ms": end_ms,
                "description": "画面变化",
                "screen_text": [],
                "confidence": 0.8,
            }
        ],
        "observations": [],
        "uncertainties": [],
    }


def test_server_advertises_its_pixel_art_icon() -> None:
    options = mcp._mcp_server.create_initialization_options()
    assert options.icons is not None
    assert len(options.icons) == 2
    assert all(icon.src.startswith("data:image/png;base64,") for icon in options.icons)
    assert all(icon.mimeType == "image/png" for icon in options.icons)
    assert [icon.sizes for icon in options.icons] == [["64x64"], ["1024x1024"]]


def test_parse_allows_only_a_full_json_object() -> None:
    parsed = parse_analysis_payload("```json\n" + json.dumps(_payload()) + "\n```")
    assert parsed.summary == "测试视频"
    with pytest.raises(ValueError, match="after the JSON"):
        parse_analysis_payload(json.dumps(_payload()) + " trailing")


def test_parse_repairs_syntax_and_caps_lists() -> None:
    malformed = r"""{"summary":"内容包含"未转义"引号","answer":"ok","timeline":[{"start_ms":0,"end_ms":1000,"description":"x","screen_text":["0","1","2","3","4","5","6","7","8","9","10"],"confidence":0.8}],"observations":[],"uncertainties":[]}"""
    warnings: list[str] = []
    parsed = parse_analysis_payload(malformed, warnings)
    assert parsed.summary == '内容包含"未转义"引号'
    assert len(parsed.timeline[0].screen_text) == 10
    assert "provider JSON syntax was repaired locally before validation" in warnings


def test_full_coverage_rejects_early_end() -> None:
    parsed = parse_analysis_payload(json.dumps(_payload(end_ms=6_500)))
    coverage, warnings = validate_coverage(parsed, 13_370, require_full_coverage=True)
    assert coverage.timestamp_valid is False
    assert "timeline does not cover the end of the video" in warnings


def test_question_does_not_require_full_coverage() -> None:
    parsed = parse_analysis_payload(json.dumps(_payload(end_ms=1_500)))
    coverage, warnings = validate_coverage(parsed, 13_370, require_full_coverage=False)
    assert coverage.timestamp_valid is True
    assert warnings == []
