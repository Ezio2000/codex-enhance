"""Public generic analysis profiles."""

from __future__ import annotations

from typing import Literal

from .contracts import ProfileName

AnalysisOperation = Literal["summary", "question", "timeline", "ocr"]
RequestedProfile = Literal["auto", "balanced", "temporal", "ocr"]


DEFAULT_PROMPTS: dict[AnalysisOperation, str] = {
    "summary": "完整概括视频中的主要画面、操作和明显变化，并给出覆盖全片的简洁时间线。",
    "question": "回答用户关于视频画面的具体问题，并给出支持答案的时间片段。",
    "timeline": "生成覆盖全片的操作时间线，重点识别界面切换、点击、输入和滚动。",
    "ocr": "提取画面中与任务有关、能够确认的关键文字，并标注出现时间。",
}


def resolve_profile(
    operation: AnalysisOperation, requested: RequestedProfile
) -> ProfileName:
    if requested != "auto":
        return requested
    if operation == "timeline":
        return "temporal"
    if operation == "ocr":
        return "ocr"
    return "balanced"
