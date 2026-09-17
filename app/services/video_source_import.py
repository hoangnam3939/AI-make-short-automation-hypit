"""Agent phân tích nguồn VIDEO (KH App new AI-make-short-automation.docx,
Nhánh 1 Bước 2: "người dùng gửi link video lên... TikTok video, youtube
video... AGENT này cao cấp hơn nữa") — bản "cao cấp hơn" của
story_import.py (link bài báo) vì video không có sẵn chữ để đọc thẳng,
phải qua "cái tai" (app/services/video_transcribe.py) tách giọng nói
thành chữ trước.

Sau khi có transcript, module này làm 2 việc KHÁC NHAU, tuỳ mục đích:
1. extract_text_from_video_url() — trả về transcript thô, để tái dùng
   NGUYÊN VẸN story_import.apply_import_mode() (follow/shorten/extract/
   custom) giống hệt luồng link bài báo -> ra câu chuyện cho Ô ý tưởng.
2. analyze_viral_formula() — KHÁC câu chuyện: "ngửi" ra CÔNG THỨC làm
   video đó viral (kiểu hook, nhịp dựng, CTA...) để dùng làm mẫu tham
   khảo khi viết 1 câu chuyện MỚI theo đúng công thức đó (không chép lại
   nguyên nội dung video gốc — tránh trùng lặp nội dung), hoặc để
   app/services/content_calendar.py dùng khi "lập thực đơn shu theo 1
   kênh/video đang viral" (KH App new, Bước 1c nhánh 2 automation)."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services import llm, video_transcribe

# Giới hạn ký tự transcript gửi cho LLM — cùng lý do MAX_RAW_CHARS ở
# story_import.py (tránh video quá dài làm chậm/vượt ngân sách token vô
# ích); 20000 ký tự đủ dư cho video ngắn (vài phút lời nói).
MAX_TRANSCRIPT_CHARS = 20000


def extract_text_from_video_url(url: str, model_size: str | None = None) -> str:
    """"Cái tai" + đọc lại: tải video, tách giọng nói thành chữ. Trả về
    ĐÚNG transcript thô (chưa qua LLM xử lý) — gọi tiếp
    story_import.apply_import_mode(text, mode, ...) để ra câu chuyện sạch,
    giống hệt luồng link bài báo (xem app/api/story.py)."""
    kwargs = {"model_size": model_size} if model_size else {}
    result = video_transcribe.transcribe_video_url(url, **kwargs)
    return result.text


@dataclass
class ViralFormula:
    hook_pattern: str = ""
    structure_beats: list[str] = field(default_factory=list)
    pacing_style: str = ""
    cta_type: str = ""
    tone: str = ""
    why_it_works: str = ""


_FORMULA_SYSTEM_PROMPT = """Bạn là chuyên gia phân tích video ngắn viral (TikTok/YouTube Shorts/Reels).
Nhận lời nói (transcript) đã tách ra từ 1 video đang viral, hãy "ngửi" ra
CÔNG THỨC làm video đó thu hút — KHÔNG kể lại nội dung/câu chuyện của video
gốc, chỉ mô tả CẤU TRÚC/KỸ THUẬT kể chuyện để áp dụng cho 1 nội dung khác:

- hook_pattern: 3 giây đầu dùng kiểu mở đầu gì để giữ chân người xem (VD
  "câu hỏi gây tò mò", "số liệu gây sốc", "vào thẳng cao trào rồi mới giải
  thích"...).
- structure_beats: liệt kê các NHỊP chính theo đúng trình tự xuất hiện
  (VD ["Hook gây tò mò", "Đặt vấn đề", "Twist bất ngờ", "Giải pháp", "CTA"]).
- pacing_style: nhịp dựng nhanh/chậm, có twist giữa video không, độ dài
  trung bình mỗi nhịp.
- cta_type: lời kêu gọi hành động cuối video thuộc kiểu gì (theo dõi, để
  lại bình luận, xem phần 2...).
- tone: giọng điệu/cảm xúc chủ đạo.
- why_it_works: 1-2 câu giải thích NGẮN GỌN vì sao công thức này hiệu quả
  với người xem video ngắn.

QUAN TRỌNG: đây là phân tích CẤU TRÚC để tham khảo áp dụng cho nội dung
MỚI, không phải tóm tắt/chép lại câu chuyện của video gốc.

Trả lời CHỈ 1 khối JSON hợp lệ bọc giữa 2 dòng đánh dấu:
===FORMULA_BAT_DAU===
{"hook_pattern": "...", "structure_beats": ["...", "..."], "pacing_style": "...",
"cta_type": "...", "tone": "...", "why_it_works": "..."}
===FORMULA_KET_THUC==="""


def analyze_viral_formula(transcript: str, effort: str = "medium") -> ViralFormula:
    """Bước "ngửi" ra công thức — xem docstring module. `transcript` là kết
    quả extract_text_from_video_url() (hoặc transcript có sẵn từ nơi
    khác)."""
    if not transcript.strip():
        raise ValueError("Không có nội dung lời nói nào để phân tích.")
    data = llm.generate_json(
        _FORMULA_SYSTEM_PROMPT, f"Transcript video:\n\n{transcript[:MAX_TRANSCRIPT_CHARS]}",
        "===FORMULA_BAT_DAU===", "===FORMULA_KET_THUC===",
        max_tokens=1200, effort=effort, default={}, raise_on_error=True,
    )
    beats = data.get("structure_beats", [])
    return ViralFormula(
        hook_pattern=str(data.get("hook_pattern", "")).strip(),
        structure_beats=[str(b).strip() for b in beats] if isinstance(beats, list) else [],
        pacing_style=str(data.get("pacing_style", "")).strip(),
        cta_type=str(data.get("cta_type", "")).strip(),
        tone=str(data.get("tone", "")).strip(),
        why_it_works=str(data.get("why_it_works", "")).strip(),
    )
