"""Test app/services/story_import.py (Bước 1 mở rộng: đính kèm câu chuyện
gốc từ file/link thay vì gõ tay). File .docx dựng THẬT bằng chính
python-docx (không mock) — đúng tinh thần dự án chỉ mock phần thật sự cần
mạng/thông tin đăng nhập (Claude, tải trang web). .pdf mock PdfReader vì
dựng 1 file PDF hợp lệ bằng tay tốn công không cần thiết cho 1 lớp parse
thuần tuý, không phải phụ thuộc ngoài cần thật."""
import io

import pytest

from app.services import story_import


def _make_docx_bytes(paragraphs: list[str]) -> bytes:
    from docx import Document

    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_extract_text_from_docx_real_file():
    content = _make_docx_bytes(["Ngày xưa có một chú chó.", "Chú chó đi lạc đường."])
    text = story_import.extract_text_from_file("cau_chuyen.docx", content)
    assert "Ngày xưa có một chú chó." in text
    assert "Chú chó đi lạc đường." in text


def test_extract_text_from_txt_file():
    text = story_import.extract_text_from_file("cau_chuyen.txt", "Nội dung văn bản thuần.".encode("utf-8"))
    assert text == "Nội dung văn bản thuần."


def test_extract_text_from_pdf_file(monkeypatch):
    class FakePage:
        def extract_text(self):
            return "Trang PDF có chữ."

    class FakeReader:
        def __init__(self, _stream):
            self.pages = [FakePage(), FakePage()]

    monkeypatch.setattr(story_import, "PdfReader", FakeReader)
    text = story_import.extract_text_from_file("tai_lieu.pdf", b"%PDF-fake-bytes")
    assert text.count("Trang PDF có chữ.") == 2


def test_extract_text_from_unreadable_binary_file_raises():
    with pytest.raises(ValueError, match="Không đọc được"):
        story_import.extract_text_from_file("anh.png", b"\x89PNG\r\n\x1a\n\xff\xfe\x00\x01")


def test_extract_text_from_url_strips_nav_and_script(monkeypatch):
    fake_html = """
    <html><body>
      <nav>Menu điều hướng</nav>
      <script>var x = 1;</script>
      <article><p>Đây là nội dung câu chuyện thật.</p></article>
      <footer>Bản quyền 2026</footer>
    </body></html>
    """

    class FakeResponse:
        text = fake_html

        def raise_for_status(self):
            return None

    def fake_get(url, timeout=20, follow_redirects=True, headers=None):
        return FakeResponse()

    monkeypatch.setattr(story_import.httpx, "get", fake_get)
    text = story_import.extract_text_from_url("https://example.com/bai-viet")
    assert "Đây là nội dung câu chuyện thật." in text
    assert "Menu điều hướng" not in text
    assert "var x = 1" not in text
    assert "Bản quyền 2026" not in text


def test_extract_text_from_url_raises_on_http_error(monkeypatch):
    import httpx as httpx_module

    def fake_get(url, timeout=20, follow_redirects=True, headers=None):
        raise httpx_module.ConnectError("không kết nối được")

    monkeypatch.setattr(story_import.httpx, "get", fake_get)
    with pytest.raises(ValueError, match="Không tải được"):
        story_import.extract_text_from_url("https://khong-ton-tai.invalid/bai")


def test_apply_import_mode_rejects_unknown_mode():
    with pytest.raises(ValueError, match="mode phải là"):
        story_import.apply_import_mode("văn bản", "khong-hop-le")


def test_apply_import_mode_rejects_empty_text():
    with pytest.raises(ValueError, match="Không có nội dung"):
        story_import.apply_import_mode("   ", "follow")


@pytest.mark.parametrize("mode", ["follow", "shorten", "extract"])
def test_apply_import_mode_calls_llm_with_mode_specific_instruction(monkeypatch, mode):
    """3 chế độ có câu lệnh mẫu sẵn — "custom" test riêng ở
    test_apply_import_mode_custom_uses_user_instruction_verbatim vì không
    có mẫu trong _MODE_INSTRUCTIONS."""
    captured = {}

    def fake_generate_text(system, user_prompt, max_tokens=8000, effort="high"):
        captured["system"] = system
        captured["user_prompt"] = user_prompt
        return "kết quả đã xử lý"

    monkeypatch.setattr(story_import.llm, "generate_text", fake_generate_text)
    result = story_import.apply_import_mode("Văn bản thô cần xử lý.", mode)

    assert result == "kết quả đã xử lý"
    assert captured["system"] == (
        "Bạn là trợ lý biên tập nội dung. " + story_import._MODE_INSTRUCTIONS[mode] +
        " Viết bằng CHÍNH ngôn ngữ của văn bản gốc bên dưới (trừ khi yêu cầu "
        "ở trên nói rõ ngôn ngữ khác). Chỉ trả về đúng phần nội dung câu "
        "chuyện, không thêm lời dẫn/giải thích/tiêu đề mục của riêng bạn."
    )
    assert captured["user_prompt"] == "Văn bản thô cần xử lý."


def test_apply_import_mode_custom_requires_instruction():
    with pytest.raises(ValueError, match="cần bạn nhập yêu cầu"):
        story_import.apply_import_mode("văn bản thô", "custom")
    with pytest.raises(ValueError, match="cần bạn nhập yêu cầu"):
        story_import.apply_import_mode("văn bản thô", "custom", custom_instruction="   ")


def test_apply_import_mode_custom_uses_user_instruction_verbatim(monkeypatch):
    captured = {}

    def fake_generate_text(system, user_prompt, max_tokens=8000, effort="high"):
        captured["system"] = system
        return "kết quả tự nhập"

    monkeypatch.setattr(story_import.llm, "generate_text", fake_generate_text)
    result = story_import.apply_import_mode(
        "văn bản thô", "custom", custom_instruction="Viết lại theo góc nhìn ngôi thứ nhất."
    )

    assert result == "kết quả tự nhập"
    assert "Viết lại theo góc nhìn ngôi thứ nhất." in captured["system"]
    # Không được lẫn 1 trong 3 câu lệnh mẫu (follow/shorten/extract) vào chế độ custom.
    for other_mode, instruction in story_import._MODE_INSTRUCTIONS.items():
        assert instruction not in captured["system"]


def test_apply_import_mode_truncates_very_long_text(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        story_import.llm, "generate_text",
        lambda system, user_prompt, max_tokens=8000, effort="high": captured.setdefault("len", len(user_prompt)) or "ok",
    )
    story_import.apply_import_mode("x" * (story_import.MAX_RAW_CHARS + 5000), "follow")
    assert captured["len"] == story_import.MAX_RAW_CHARS
