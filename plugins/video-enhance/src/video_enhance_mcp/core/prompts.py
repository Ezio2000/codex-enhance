"""Provider-neutral structured video-understanding prompt."""

from __future__ import annotations


def build_video_prompt(user_prompt: str, duration_ms: int | None) -> str:
    duration_instruction = ""
    if duration_ms is not None:
        duration_instruction = f"""
已知原视频总时长为 {duration_ms} 毫秒。所有 start_ms/end_ms 必须使用原视频真实毫秒时间，
范围必须在 0 到 {duration_ms} 之间。不要把内部帧序号、归一化位置或 0.1/0.2 标签当作秒数。
"""

    return f"""你正在分析一段视频。只依据可见画面，不要声称听到了音频。

服务器在原画面下方添加了黑色时间码栏；`SOURCE_TIME HH:MM:SS.mmm` 是该帧在原视频中的
权威时间，`TOTAL_MS` 是原视频总时长。时间线必须读取这个时间码，黑色栏不属于原视频内容。

用户任务：
{user_prompt}
{duration_instruction}
请返回一个压缩 JSON 对象，不要 Markdown、代码围栏、解释或思考过程。
JSON 必须符合以下结构：
{{
  "summary": "视频概述",
  "answer": "对用户任务的直接回答",
  "timeline": [
    {{
      "start_ms": 0,
      "end_ms": 1000,
      "description": "该时间段能确认的画面事件",
      "screen_text": ["能确认的屏幕文字"],
      "confidence": 0.0
    }}
  ],
  "observations": ["其他重要可见事实"],
  "uncertainties": ["无法从画面确认的内容"]
}}

约束：timeline 最多 20 项；每项 screen_text 最多 10 项、每项最多 120 字；
observations 最多 30 项；uncertainties 最多 20 项。不确定时明确说明，不要猜测。
JSON 字符串内部出现的双引号必须转义。不要在 summary 或 answer 中把 uncertainties 里的推测写成事实。
若用户任务不需要完整时间线，可只返回与问题有关的片段。
""".strip()
