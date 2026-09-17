"""Test 2 endpoint mới của app/api/story.py cho Agent "ngửi công thức từ
video hot": POST /story/import-video-url và POST /story/video-formula."""
from fastapi.testclient import TestClient

from app.api import story as story_api
from app.main import app
from app.services.llm import LlmNotConfiguredError
from app.services.video_transcribe import TranscribeNotConfiguredError

client = TestClient(app)


def test_import_video_url_rejects_invalid_mode():
    res = client.post(
        "/api/story/import-video-url", json={"url": "https://tiktok.com/@x/video/1", "mode": "sai"}
    )
    assert res.status_code == 400


def test_import_video_url_success(monkeypatch):
    monkeypatch.setattr(
        story_api.video_source_import, "extract_text_from_video_url", lambda url: "transcript video"
    )
    monkeypatch.setattr(
        story_api.story_import, "apply_import_mode",
        lambda text, mode, custom_instruction=None: f"[{mode}] {text}",
    )
    res = client.post(
        "/api/story/import-video-url",
        json={"url": "https://tiktok.com/@x/video/1", "mode": "extract"},
    )
    assert res.status_code == 200
    assert res.json() == {"story": "[extract] transcript video"}


def test_import_video_url_transcribe_not_configured_returns_400(monkeypatch):
    def raise_not_configured(url):
        raise TranscribeNotConfiguredError("Chưa cài yt-dlp trên máy này.")

    monkeypatch.setattr(story_api.video_source_import, "extract_text_from_video_url", raise_not_configured)
    res = client.post(
        "/api/story/import-video-url",
        json={"url": "https://tiktok.com/@x/video/1", "mode": "follow"},
    )
    assert res.status_code == 400
    assert "yt-dlp" in res.json()["detail"]


def test_import_video_url_download_failure_returns_400(monkeypatch):
    def raise_value_error(url):
        raise ValueError("Không tải được video/audio từ link này")

    monkeypatch.setattr(story_api.video_source_import, "extract_text_from_video_url", raise_value_error)
    res = client.post(
        "/api/story/import-video-url",
        json={"url": "https://tiktok.com/@x/video/broken", "mode": "follow"},
    )
    assert res.status_code == 400
    assert "Không tải được" in res.json()["detail"]


def test_import_video_url_llm_not_configured_returns_400(monkeypatch):
    monkeypatch.setattr(
        story_api.video_source_import, "extract_text_from_video_url", lambda url: "transcript"
    )

    def raise_not_configured(text, mode, custom_instruction=None):
        raise LlmNotConfiguredError("Chưa cấu hình LLM")

    monkeypatch.setattr(story_api.story_import, "apply_import_mode", raise_not_configured)
    res = client.post(
        "/api/story/import-video-url",
        json={"url": "https://tiktok.com/@x/video/1", "mode": "follow"},
    )
    assert res.status_code == 400
    assert "Chưa cấu hình" in res.json()["detail"]


def test_video_formula_success(monkeypatch):
    monkeypatch.setattr(
        story_api.video_source_import, "extract_text_from_video_url", lambda url: "transcript video"
    )

    class FakeFormula:
        hook_pattern = "câu hỏi gây tò mò"
        structure_beats = ["Hook", "Twist", "CTA"]
        pacing_style = "nhanh"
        cta_type = "theo dõi"
        tone = "hài hước"
        why_it_works = "Twist bất ngờ giữ chân người xem."

    monkeypatch.setattr(story_api.video_source_import, "analyze_viral_formula", lambda transcript: FakeFormula())
    res = client.post("/api/story/video-formula", json={"url": "https://tiktok.com/@x/video/1"})
    assert res.status_code == 200
    body = res.json()
    assert body["hook_pattern"] == "câu hỏi gây tò mò"
    assert body["structure_beats"] == ["Hook", "Twist", "CTA"]


def test_video_formula_transcribe_failure_returns_400(monkeypatch):
    def raise_value_error(url):
        raise ValueError("Không nhận ra lời nói nào trong video này")

    monkeypatch.setattr(story_api.video_source_import, "extract_text_from_video_url", raise_value_error)
    res = client.post("/api/story/video-formula", json={"url": "https://tiktok.com/@x/video/silent"})
    assert res.status_code == 400
    assert "Không nhận ra lời nói" in res.json()["detail"]
