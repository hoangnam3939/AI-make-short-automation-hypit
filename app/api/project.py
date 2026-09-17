from enum import Enum
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()

# 20 ngôn ngữ đề xuất — đúng danh sách Mục 6, Nhiem_Vu_Goc_App_Video_AI_V3.docx.
# Mã giọng theo edge-tts (voice locale), dùng chung cho ngôn ngữ giao diện (6.1)
# và ngôn ngữ giọng đọc video (6.2).
SUPPORTED_LANGUAGES = [
    {"code": "en-US", "name": "Tiếng Anh"},
    {"code": "vi-VN", "name": "Tiếng Việt"},
    {"code": "zh-CN", "name": "Tiếng Trung"},
    {"code": "es-ES", "name": "Tiếng Tây Ban Nha"},
    {"code": "ru-RU", "name": "Tiếng Nga"},
    {"code": "ar-SA", "name": "Tiếng Ả Rập"},
    {"code": "hi-IN", "name": "Tiếng Hindi"},
    {"code": "pt-BR", "name": "Tiếng Bồ Đào Nha (Brazil)"},
    {"code": "fr-FR", "name": "Tiếng Pháp"},
    {"code": "ja-JP", "name": "Tiếng Nhật"},
    {"code": "tr-TR", "name": "Tiếng Thổ Nhĩ Kỳ"},
    {"code": "de-DE", "name": "Tiếng Đức"},
    {"code": "ko-KR", "name": "Tiếng Hàn"},
    {"code": "id-ID", "name": "Tiếng Indonesia"},
    {"code": "th-TH", "name": "Tiếng Thái"},
    {"code": "it-IT", "name": "Tiếng Ý"},
    {"code": "pl-PL", "name": "Tiếng Ba Lan"},
    {"code": "bn-IN", "name": "Tiếng Bengal"},
    {"code": "ur-PK", "name": "Tiếng Urdu"},
    {"code": "nl-NL", "name": "Tiếng Hà Lan"},
]
_VALID_CODES = {lang["code"] for lang in SUPPORTED_LANGUAGES}


class VideoFormat(str, Enum):
    long = "long"   # 16:9, phút
    short = "short"  # 9:16, giây


class ProjectInput(BaseModel):
    idea_or_story: str = Field(..., min_length=1, description="Ý tưởng hoặc câu chuyện gốc")
    format: VideoFormat
    duration_minutes: int | None = Field(
        None, description="Bắt buộc nếu format=long: 1-30 phút (7 nút có sẵn hoặc kéo thanh trượt chọn số bất kỳ)"
    )
    duration_seconds: int | None = Field(
        None, description="Bắt buộc nếu format=short: 1-60 giây (4 nút có sẵn hoặc kéo thanh trượt chọn số bất kỳ)"
    )
    output_languages: List[str] = Field(..., min_length=1, description="Mã ngôn ngữ giọng đọc video, chọn nhiều được")


# 7 mốc có nút bấm sẵn — vẫn giữ để hiển thị gợi ý, nhưng KHÔNG còn là tập
# giá trị hợp lệ DUY NHẤT: thanh trượt dọc (app.js::setupDurationSlider) cho
# phép chọn bất kỳ số phút 1-30 / số giây 1-60 nào, xem LONG_DURATION_RANGE/
# SHORT_DURATION_RANGE bên dưới.
LONG_DURATIONS = {5, 7, 10, 15, 20, 25, 30}
SHORT_DURATIONS = {15, 24, 30, 60}
LONG_DURATION_RANGE = range(1, 31)   # 1-30 phút
SHORT_DURATION_RANGE = range(1, 61)  # 1-60 giây


@router.get("/languages")
def list_languages():
    return {"languages": SUPPORTED_LANGUAGES}


@router.post("/project")
def create_project(payload: ProjectInput):
    """Bước 0 của luồng (Mục 2, V3): nhận input màn hình 1.

    STUB giai đoạn 1 — chưa gọi LLM viết kịch bản (Bước 1-4, Mục 3, V3).
    Chỉ validate input và trả lại để xác nhận backend/frontend đã nối
    đúng nhau.
    """
    if payload.format == VideoFormat.long:
        if payload.duration_minutes not in LONG_DURATION_RANGE:
            raise HTTPException(400, f"duration_minutes phải trong khoảng {LONG_DURATION_RANGE.start}-{LONG_DURATION_RANGE.stop - 1} phút")
    else:
        if payload.duration_seconds not in SHORT_DURATION_RANGE:
            raise HTTPException(400, f"duration_seconds phải trong khoảng {SHORT_DURATION_RANGE.start}-{SHORT_DURATION_RANGE.stop - 1} giây")

    unknown = [c for c in payload.output_languages if c not in _VALID_CODES]
    if unknown:
        raise HTTPException(400, f"Mã ngôn ngữ không hợp lệ: {unknown}")

    return {
        "status": "received",
        "next_step": "Bước 1 (viết lại câu chuyện đầy đủ) — chưa triển khai, xem README.md",
        "echo": payload,
    }
