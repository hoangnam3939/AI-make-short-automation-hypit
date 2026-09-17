from fastapi.testclient import TestClient

from app.api import story as story_api
from app.main import app
from app.services.llm import LlmNotConfiguredError

client = TestClient(app)


def test_import_file_rejects_invalid_mode():
    res = client.post(
        "/api/story/import-file",
        data={"mode": "khong-hop-le"},
        files={"file": ("truyen.txt", b"noi dung", "text/plain")},
    )
    assert res.status_code == 400


def test_import_file_returns_400_on_unreadable_content(monkeypatch):
    res = client.post(
        "/api/story/import-file",
        data={"mode": "follow"},
        files={"file": ("anh.png", b"\x89PNG\xff\xfe", "image/png")},
    )
    assert res.status_code == 400


def test_import_file_success(monkeypatch):
    monkeypatch.setattr(story_api.story_import, "extract_text_from_file", lambda filename, content: "văn bản thô")
    monkeypatch.setattr(
        story_api.story_import, "apply_import_mode",
        lambda text, mode, custom_instruction=None: f"[{mode}] {text}",
    )

    res = client.post(
        "/api/story/import-file",
        data={"mode": "shorten"},
        files={"file": ("truyen.docx", b"fake docx bytes", "application/octet-stream")},
    )
    assert res.status_code == 200
    assert res.json() == {"story": "[shorten] văn bản thô"}


def test_import_file_llm_not_configured_returns_400(monkeypatch):
    monkeypatch.setattr(story_api.story_import, "extract_text_from_file", lambda filename, content: "văn bản thô")

    def raise_not_configured(text, mode, custom_instruction=None):
        raise LlmNotConfiguredError("Chưa cấu hình LLM")

    monkeypatch.setattr(story_api.story_import, "apply_import_mode", raise_not_configured)

    res = client.post(
        "/api/story/import-file",
        data={"mode": "follow"},
        files={"file": ("truyen.txt", b"noi dung", "text/plain")},
    )
    assert res.status_code == 400
    assert "Chưa cấu hình" in res.json()["detail"]


def test_import_url_rejects_invalid_mode():
    res = client.post("/api/story/import-url", json={"url": "https://vi.wikipedia.org/x", "mode": "sai"})
    assert res.status_code == 400


def test_import_url_success(monkeypatch):
    monkeypatch.setattr(story_api.story_import, "extract_text_from_url", lambda url: "văn bản từ trang web")
    monkeypatch.setattr(
        story_api.story_import, "apply_import_mode",
        lambda text, mode, custom_instruction=None: f"[{mode}] {text}",
    )

    res = client.post(
        "/api/story/import-url", json={"url": "https://vi.wikipedia.org/wiki/Thanh_Giong", "mode": "extract"}
    )
    assert res.status_code == 200
    assert res.json() == {"story": "[extract] văn bản từ trang web"}


def test_import_file_custom_mode_passes_instruction_through(monkeypatch):
    captured = {}
    monkeypatch.setattr(story_api.story_import, "extract_text_from_file", lambda filename, content: "văn bản thô")

    def fake_apply(text, mode, custom_instruction=None):
        captured["mode"] = mode
        captured["custom_instruction"] = custom_instruction
        return "kết quả tự nhập"

    monkeypatch.setattr(story_api.story_import, "apply_import_mode", fake_apply)

    res = client.post(
        "/api/story/import-file",
        data={"mode": "custom", "custom_instruction": "Viết lại theo phong cách hài hước."},
        files={"file": ("truyen.txt", b"noi dung", "text/plain")},
    )
    assert res.status_code == 200
    assert res.json() == {"story": "kết quả tự nhập"}
    assert captured == {"mode": "custom", "custom_instruction": "Viết lại theo phong cách hài hước."}


def test_import_file_custom_mode_without_instruction_returns_400():
    """Không mock apply_import_mode — kiểm tra thật đường dẫn ValueError (từ
    story_import.apply_import_mode) -> HTTPException 400 hoạt động đúng."""
    res = client.post(
        "/api/story/import-file",
        data={"mode": "custom"},
        files={"file": ("truyen.txt", "Nội dung thật.".encode("utf-8"), "text/plain")},
    )
    assert res.status_code == 400
    assert "cần bạn nhập yêu cầu" in res.json()["detail"]


def test_import_url_custom_mode_passes_instruction_through(monkeypatch):
    captured = {}
    monkeypatch.setattr(story_api.story_import, "extract_text_from_url", lambda url: "văn bản từ trang web")

    def fake_apply(text, mode, custom_instruction=None):
        captured["custom_instruction"] = custom_instruction
        return "kết quả tự nhập"

    monkeypatch.setattr(story_api.story_import, "apply_import_mode", fake_apply)

    res = client.post(
        "/api/story/import-url",
        json={"url": "https://vi.wikipedia.org/x", "mode": "custom", "custom_instruction": "Ghép 2 câu chuyện lại."},
    )
    assert res.status_code == 200
    assert captured["custom_instruction"] == "Ghép 2 câu chuyện lại."


def test_import_url_fetch_failure_returns_400(monkeypatch):
    def raise_value_error(url):
        raise ValueError("Không tải được nội dung từ link này")

    monkeypatch.setattr(story_api.story_import, "extract_text_from_url", raise_value_error)

    res = client.post("/api/story/import-url", json={"url": "https://khong-ton-tai.invalid", "mode": "follow"})
    assert res.status_code == 400
    assert "Không tải được" in res.json()["detail"]
