"""Bước 1-4 (Mục 3, V3) qua API — viết lại câu chuyện + viết kịch bản.

Cần ANTHROPIC_API_KEY đã cấu hình ở /api/settings/api-key; nếu chưa có,
trả 400 với thông báo rõ ràng thay vì lỗi 500 khó hiểu.
"""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.services import script_writer, story_import, video_source_import, video_transcribe
from app.services.llm import LlmCliError, LlmNotConfiguredError, LlmRefusalError

router = APIRouter()


def _call_llm_or_400(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except LlmNotConfiguredError as e:
        raise HTTPException(400, str(e))
    except LlmRefusalError as e:
        raise HTTPException(422, str(e))
    except LlmCliError as e:
        # Lỗi CLI thật (hết hạn mức phiên Claude Pro/Max, chưa đăng nhập,
        # timeout...) — PHẢI trả nguyên văn lý do cho người dùng thấy, nếu
        # không sẽ lọt thành lỗi 500 chung chung, người dùng chỉ thấy
        # "thất bại, thử lại" lặp vô ích mà không biết vì sao (lỗi thật đã
        # gặp: "You've hit your session limit — resets 3pm").
        raise HTTPException(503, str(e))


class RewriteStoryInput(BaseModel):
    idea_or_story: str = Field(..., min_length=1)


@router.post("/story/rewrite")
def rewrite_story(payload: RewriteStoryInput):
    story = _call_llm_or_400(script_writer.rewrite_story, payload.idea_or_story)
    return {"story": story}


class ThemeFields(BaseModel):
    """Bước 3 (Mục 3, V3) — đối tượng xem/vấn đề họ quan tâm/thông điệp
    chính/góc triển khai. Dùng chung cho cả input (khi gửi kèm Bước 4/5) lẫn
    output (kết quả trả về từ /story/theme)."""
    target_audience: str = ""
    audience_pain_point: str = ""
    core_message: str = ""
    best_angle: str = ""


class ThemeInput(BaseModel):
    story: str = Field(..., min_length=1)


@router.post("/story/theme")
def post_theme(payload: ThemeInput):
    theme = _call_llm_or_400(script_writer.determine_theme_and_goals, payload.story)
    return {
        "target_audience": theme.target_audience,
        "audience_pain_point": theme.audience_pain_point,
        "core_message": theme.core_message,
        "best_angle": theme.best_angle,
    }


class HooksInput(BaseModel):
    story: str = Field(..., min_length=1)
    theme: ThemeFields | None = None


@router.post("/story/hooks")
def post_hooks(payload: HooksInput):
    """Bước 4 — 20 câu hook chia 5 nhóm + 3 câu mạnh nhất. `theme` (tuỳ
    chọn) là kết quả Bước 3 đã có, giúp hook bám đúng đối tượng/thông điệp."""
    theme_obj = script_writer.ThemeAndGoals(**payload.theme.model_dump()) if payload.theme else None
    result = _call_llm_or_400(script_writer.generate_hooks, payload.story, theme_obj)
    return {
        "candidates": [{"group": c.group, "text": c.text} for c in result.candidates],
        "top_3": result.top_3,
    }


class GenerateScriptInput(BaseModel):
    story: str = Field(..., min_length=1)
    is_long_format: bool
    duration_minutes: int | None = None
    duration_seconds: int | None = None
    language_name: str = "Tiếng Việt"
    theme: ThemeFields | None = None
    chosen_hook: str | None = None


@router.post("/story/script")
def generate_script(payload: GenerateScriptInput):
    if payload.is_long_format and payload.duration_minutes is None:
        raise HTTPException(400, "duration_minutes bắt buộc khi is_long_format=true")
    if not payload.is_long_format and payload.duration_seconds is None:
        raise HTTPException(400, "duration_seconds bắt buộc khi is_long_format=false")

    theme_obj = script_writer.ThemeAndGoals(**payload.theme.model_dump()) if payload.theme else None
    result = _call_llm_or_400(
        script_writer.generate_script,
        story=payload.story,
        is_long_format=payload.is_long_format,
        duration_minutes=payload.duration_minutes,
        duration_seconds=payload.duration_seconds,
        language_name=payload.language_name,
        theme=theme_obj,
        chosen_hook=payload.chosen_hook,
    )
    # Skill 11 (narration-length-budget): kèm số liệu ngân sách từ để giao
    # diện cảnh báo NGAY nếu Claude lỡ viết dài hơn dự kiến — chỉ cảnh báo,
    # không tự động cắt bớt lời đọc (người dùng tự sửa lại nếu cần).
    return {
        "script": result.text,
        "narration_word_count": result.actual_word_count,
        "narration_target_word_count": result.target_word_count,
        "narration_over_budget": result.over_budget,
    }


def _import_or_400(raw_text_fn, mode: str, custom_instruction: str | None):
    try:
        raw_text = raw_text_fn()
    except ValueError as e:
        raise HTTPException(400, str(e))
    try:
        story = _call_llm_or_400(story_import.apply_import_mode, raw_text, mode, custom_instruction)
    except ValueError as e:
        # VD mode="custom" nhưng thiếu custom_instruction — lỗi người dùng
        # nhập thiếu, không phải lỗi LLM, nên _call_llm_or_400 không bắt được.
        raise HTTPException(400, str(e))
    return {"story": story}


@router.post("/story/import-file")
async def import_story_file(
    mode: str = Form(...), file: UploadFile = File(...), custom_instruction: str | None = Form(None)
):
    """Bước 1, đính kèm câu chuyện gốc từ file (.docx/.pdf/văn bản thuần)
    thay vì gõ tay — xem app/services/story_import.py."""
    if mode not in story_import.IMPORT_MODES:
        raise HTTPException(400, f"mode phải là 1 trong {story_import.IMPORT_MODES}")
    content = await file.read()
    return _import_or_400(
        lambda: story_import.extract_text_from_file(file.filename or "upload", content),
        mode, custom_instruction,
    )


class ImportUrlInput(BaseModel):
    url: str = Field(..., min_length=1)
    mode: str = Field(..., description=f"1 trong {story_import.IMPORT_MODES}")
    custom_instruction: str | None = None


@router.post("/story/import-url")
def import_story_url(payload: ImportUrlInput):
    """Bước 1, đính kèm câu chuyện gốc từ link 1 bài viết trên mạng — xem
    app/services/story_import.py. (Link tới VIDEO: dùng /story/import-video-url
    bên dưới, vì cần tách giọng nói thành chữ trước.)"""
    if payload.mode not in story_import.IMPORT_MODES:
        raise HTTPException(400, f"mode phải là 1 trong {story_import.IMPORT_MODES}")
    return _import_or_400(
        lambda: story_import.extract_text_from_url(payload.url), payload.mode, payload.custom_instruction
    )


def _video_transcript_or_400(url: str) -> str:
    """Cùng vai trò `_import_or_400` (file/link bài viết) nhưng cho link
    video — tách riêng vì lỗi thiếu yt-dlp/faster-whisper/ffmpeg
    (TranscribeNotConfiguredError) là lỗi CẤU HÌNH máy, khác lỗi "video lỗi/
    không có tiếng" (ValueError) của story_import, nhưng cả 2 đều nên báo
    400 rõ ràng cho người dùng thay vì lỗi 500 khó hiểu."""
    try:
        return video_source_import.extract_text_from_video_url(url)
    except (ValueError, video_transcribe.TranscribeNotConfiguredError) as e:
        raise HTTPException(400, str(e))


class ImportVideoUrlInput(BaseModel):
    url: str = Field(..., min_length=1)
    mode: str = Field(..., description=f"1 trong {story_import.IMPORT_MODES}")
    custom_instruction: str | None = None


@router.post("/story/import-video-url")
def import_story_video_url(payload: ImportVideoUrlInput):
    """Bước 1/2 (Nhánh 1), "gửi link video lên" (TikTok/YouTube viral...) —
    khác link bài báo: phải tách giọng nói thành chữ trước ("cái tai", xem
    app/services/video_transcribe.py), rồi mới xử lý giống hệt luồng link
    bài báo (story_import.apply_import_mode) để ra câu chuyện cho Ô ý
    tưởng."""
    if payload.mode not in story_import.IMPORT_MODES:
        raise HTTPException(400, f"mode phải là 1 trong {story_import.IMPORT_MODES}")
    raw_text = _video_transcript_or_400(payload.url)
    try:
        story = _call_llm_or_400(story_import.apply_import_mode, raw_text, payload.mode, payload.custom_instruction)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"story": story}


class VideoFormulaInput(BaseModel):
    url: str = Field(..., min_length=1)


@router.post("/story/video-formula")
def analyze_video_formula(payload: VideoFormulaInput):
    """"Ngửi" ra CÔNG THỨC viral của 1 video (khác câu chuyện, xem
    app/services/video_source_import.py) — dùng khi người dùng muốn học
    cấu trúc/kỹ thuật của 1 video hot để áp dụng cho nội dung mới, thay vì
    kể lại nguyên văn nội dung video gốc."""
    transcript = _video_transcript_or_400(payload.url)
    formula = _call_llm_or_400(video_source_import.analyze_viral_formula, transcript)
    return {
        "hook_pattern": formula.hook_pattern,
        "structure_beats": formula.structure_beats,
        "pacing_style": formula.pacing_style,
        "cta_type": formula.cta_type,
        "tone": formula.tone,
        "why_it_works": formula.why_it_works,
    }
