"""API cho Agent "lập thực đơn tháng" (KH App new, Bước 1c nhánh 2
automation) — xem app/services/content_calendar.py."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import content_calendar, video_source_import, video_transcribe
from app.services.llm import LlmCliError, LlmJsonParseError, LlmNotConfiguredError, LlmRefusalError

router = APIRouter()


def _call_llm_or_400(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except LlmNotConfiguredError as e:
        raise HTTPException(400, str(e))
    except LlmRefusalError as e:
        raise HTTPException(422, str(e))
    except LlmJsonParseError as e:
        # LLM trả về đúng dạng gọi thành công nhưng KHÔNG đúng số lượng/JSON hợp
        # lệ (VD lịch quá lớn bị cắt giữa mảng) — lỗi ở phía LLM, không phải lỗi
        # người dùng nhập sai, nhưng vẫn không phải lỗi server 500.
        raise HTTPException(502, str(e))
    except LlmCliError as e:
        raise HTTPException(503, str(e))


def _slot_to_dict(s: content_calendar.ScheduleSlot) -> dict:
    return {
        "day": s.day,
        "platform": s.platform,
        "publish_time": s.publish_time,
        "duration_seconds": s.duration_seconds,
        "topic": s.topic,
        "angle": s.angle,
        "hook_idea": s.hook_idea,
    }


class GenerateCalendarInput(BaseModel):
    strategy: str = Field(..., min_length=1)
    platforms: list[str] = Field(..., min_length=1)
    videos_per_day: int = Field(..., ge=1)
    days: int = Field(..., ge=1)
    duration_seconds: int = Field(..., ge=1)
    golden_hours: dict[str, str] | None = None
    # Bước 1c: "ý tưởng có thể là shu theo 1 kênh tiktok nổi tiếng đang
    # VIRAL" — 1 link video mẫu (tuỳ chọn) để phân tích công thức trước khi
    # sinh chủ đề, xem app/services/video_source_import.py.
    reference_video_url: str | None = None


@router.post("/calendar/generate")
def generate_calendar(payload: GenerateCalendarInput):
    try:
        slots = content_calendar.build_schedule_grid(
            payload.platforms, payload.videos_per_day, payload.days,
            payload.duration_seconds, payload.golden_hours,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    reference_formula = None
    if payload.reference_video_url:
        try:
            transcript = video_source_import.extract_text_from_video_url(payload.reference_video_url)
        except (ValueError, video_transcribe.TranscribeNotConfiguredError) as e:
            raise HTTPException(400, str(e))
        reference_formula = _call_llm_or_400(video_source_import.analyze_viral_formula, transcript)

    try:
        slots = _call_llm_or_400(content_calendar.generate_topics, payload.strategy, slots, reference_formula)
    except ValueError as e:
        raise HTTPException(400, str(e))

    return {
        "total_videos": len(slots),
        "strategy_summary": payload.strategy.strip(),
        "slots": [_slot_to_dict(s) for s in slots],
    }


class ScheduleSlotInput(BaseModel):
    day: int
    platform: str
    publish_time: str
    duration_seconds: int
    topic: str = ""
    angle: str = ""
    hook_idea: str = ""


class ReviseCalendarInput(BaseModel):
    slots: list[ScheduleSlotInput] = Field(..., min_length=1)
    instruction: str = Field(..., min_length=1)


@router.post("/calendar/revise")
def revise_calendar(payload: ReviseCalendarInput):
    """"Chỉnh sửa do Agent" (KH App new, Bước 1c) — người dùng đánh tay 1
    yêu cầu sửa, Agent áp dụng lên toàn bộ thực đơn đã lập, giữ nguyên
    lịch ngày/quầy/giờ."""
    slots = [
        content_calendar.ScheduleSlot(
            day=s.day, platform=s.platform, publish_time=s.publish_time,
            duration_seconds=s.duration_seconds, topic=s.topic, angle=s.angle, hook_idea=s.hook_idea,
        )
        for s in payload.slots
    ]
    try:
        slots = _call_llm_or_400(content_calendar.revise_calendar_topics, slots, payload.instruction)
    except ValueError as e:
        raise HTTPException(400, str(e))

    return {"slots": [_slot_to_dict(s) for s in slots]}
