"""Bước 1 (Mục 3, V3), mở rộng: đính kèm câu chuyện gốc từ file (Word/PDF/
văn bản bất kỳ) hoặc link internet dẫn tới 1 bài viết có câu chuyện — thay
vì chỉ dán/gõ tay vào ô "Ý tưởng hoặc câu chuyện gốc".

Người dùng chọn 1 trong 4 cách xử lý nội dung thô lấy được, TRƯỚC khi đưa
vào ô Bước 1:
- "follow"  (làm theo)   — giữ nguyên tinh thần, chỉ dọn lại cho sạch.
- "shorten" (rút gọn)    — tóm lại ngắn hơn nhưng vẫn đủ ý chính.
- "extract" (trích xuất) — chỉ lấy đúng phần nội dung câu chuyện, bỏ hết
  phần thừa (quảng cáo, điều hướng, bình luận...).
- "custom"  (tự nhập yêu cầu) — người dùng tự gõ/dán đúng câu lệnh muốn
  LLM làm gì với nội dung lấy được (VD "viết lại theo góc nhìn ngôi thứ
  nhất", "ghép nội dung này với 1 câu chuyện hiện đại"...), thay vì chọn
  1 trong 3 mẫu có sẵn ở trên — LLM nào đang cấu hình (Claude/ChatGPT/
  Gemini, xem app/services/llm.py) sẽ nhận đúng câu lệnh đó làm chỉ dẫn xử
  lý chính.

Link internet dẫn tới VIDEO (TikTok/YouTube...) có câu chuyện bằng lời
nói — KHÔNG xử lý ở module này (video không có sẵn chữ để đọc thẳng như
trang bài viết). Xem app/services/video_source_import.py +
app/services/video_transcribe.py ("cái tai" tách giọng nói thành chữ
trước, rồi mới tái dùng apply_import_mode() ở đây)."""
from __future__ import annotations

import io

import httpx
from bs4 import BeautifulSoup
from docx import Document
from pypdf import PdfReader

from app.services import llm

IMPORT_MODES = ("follow", "shorten", "extract", "custom")

# Giới hạn ký tự gửi cho LLM — tránh file/trang quá dài (ebook, bài dài kỳ)
# làm chậm hoặc vượt ngân sách token vô ích; 60000 ký tự đủ dư cho hầu hết
# truyện ngắn/bài báo/chương sách thông thường.
MAX_RAW_CHARS = 60000

_NON_STORY_NOTES_INSTRUCTION = (
    " LOẠI BỎ HOÀN TOÀN mọi mục ghi chú/phân tích không phải bản thân câu "
    "chuyện — ví dụ mục bàn về lý do nội dung này hấp dẫn để làm video (VD "
    "'Vì sao hấp dẫn để làm video'), mục ghi chú độ tin cậy nguồn/tư liệu "
    "tham khảo (VD 'Ghi chú độ tin cậy nguồn'), hoặc bất kỳ phần nào khác "
    "chỉ nói VỀ câu chuyện/tư liệu thay vì KỂ câu chuyện — đây là ghi chú "
    "sản xuất của người viết, không phải nội dung câu chuyện."
)

_MODE_INSTRUCTIONS = {
    "follow": (
        "Dọn lại nội dung dưới đây cho sạch (bỏ lỗi định dạng/ký tự thừa do "
        "trích xuất tự động từ file/trang web), GIỮ NGUYÊN toàn bộ nội dung "
        "và tinh thần câu chuyện gốc — không tóm tắt, không bỏ chi tiết nào "
        "của câu chuyện." + _NON_STORY_NOTES_INSTRUCTION
    ),
    "shorten": (
        "Rút gọn nội dung dưới đây thành bản ngắn hơn nhưng vẫn đủ ý chính, "
        "giữ đúng mạch truyện gốc, không bịa thêm chi tiết mới." + _NON_STORY_NOTES_INSTRUCTION
    ),
    "extract": (
        "Trích xuất ĐÚNG phần nội dung câu chuyện từ văn bản dưới đây — bỏ "
        "hết phần không liên quan (quảng cáo, menu điều hướng, bình luận "
        "người đọc, lời giới thiệu trang web/tác giả...), chỉ giữ lại đúng "
        "phần kể chuyện." + _NON_STORY_NOTES_INSTRUCTION
    ),
}


def extract_text_from_file(filename: str, content: bytes) -> str:
    """Đọc nội dung chữ từ file người dùng tải lên. Hỗ trợ .docx/.pdf và
    mọi file văn bản thuần (encoding UTF-8, VD .txt/.md) — file nhị phân
    không đọc được chữ (ảnh, video, file nén...) báo lỗi rõ ràng thay vì
    trả về rác cho LLM xử lý."""
    name_lower = filename.lower()
    if name_lower.endswith(".docx"):
        doc = Document(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    if name_lower.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError(
            f"Không đọc được nội dung chữ từ file '{filename}' — chỉ hỗ trợ "
            ".docx, .pdf, hoặc file văn bản thuần (VD .txt)."
        )


def extract_text_from_url(url: str) -> str:
    """Tải 1 trang bài viết và lấy phần nội dung chữ chính — bỏ các khối
    chắc chắn không phải nội dung (script/style/nav/footer/header/aside/
    form), không dùng thuật toán "readability" đầy đủ để tách đúng vùng
    nội dung chính. Đủ dùng làm nguyên liệu thô cho apply_import_mode() xử
    lý tiếp bằng LLM (LLM lọc phần rác còn sót tốt hơn heuristic HTML)."""
    try:
        resp = httpx.get(
            url, timeout=20, follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (AI Video Studio story import)"},
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise ValueError(f"Không tải được nội dung từ link này: {exc}")

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
        tag.decompose()
    lines = [ln.strip() for ln in soup.get_text(separator="\n").splitlines()]
    text = "\n".join(ln for ln in lines if ln)
    if not text.strip():
        raise ValueError("Không lấy được nội dung chữ nào từ link này.")
    return text


def apply_import_mode(raw_text: str, mode: str, custom_instruction: str | None = None) -> str:
    """Dùng LLM xử lý văn bản thô lấy được (từ file/link) theo đúng lựa
    chọn của người dùng, trả về kết quả sẵn sàng đưa vào ô "Ý tưởng hoặc
    câu chuyện gốc" (Bước 1) để người dùng xem/sửa tiếp trước khi viết
    kịch bản.

    mode="custom": dùng NGUYÊN VĂN `custom_instruction` (người dùng tự gõ)
    làm chỉ dẫn xử lý chính thay cho 1 trong 3 mẫu follow/shorten/extract —
    LLM đang cấu hình (Claude/ChatGPT/Gemini) nhận đúng câu lệnh đó."""
    if mode not in IMPORT_MODES:
        raise ValueError(f"mode phải là 1 trong {IMPORT_MODES}, nhận '{mode}'")
    if not raw_text.strip():
        raise ValueError("Không có nội dung chữ nào để xử lý.")

    if mode == "custom":
        if not custom_instruction or not custom_instruction.strip():
            raise ValueError("Chế độ 'custom' cần bạn nhập yêu cầu xử lý cụ thể.")
        instruction = custom_instruction.strip()
    else:
        instruction = _MODE_INSTRUCTIONS[mode]

    system = (
        "Bạn là trợ lý biên tập nội dung. " + instruction +
        " Viết bằng CHÍNH ngôn ngữ của văn bản gốc bên dưới (trừ khi yêu cầu "
        "ở trên nói rõ ngôn ngữ khác). Chỉ trả về đúng phần nội dung câu "
        "chuyện, không thêm lời dẫn/giải thích/tiêu đề mục của riêng bạn."
    )
    user_prompt = raw_text[:MAX_RAW_CHARS]
    return llm.generate_text(system=system, user_prompt=user_prompt, max_tokens=8000, effort="high")
