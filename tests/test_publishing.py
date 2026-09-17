"""Test cho publishing.py. KHÔNG gọi mạng thật tới bất kỳ nền tảng nào (chưa
có API key thật) — giả lập httpx để kiểm tra: (1) khi chưa cấu hình, báo
lỗi rõ ràng và KHÔNG gọi mạng; (2) khi đã cấu hình (giả), xây đúng request
(URL/payload) và xử lý đúng response giả lập thành công/thất bại."""
from __future__ import annotations

import json

import httpx
import pytest

from app.services import publishing


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path, monkeypatch):
    monkeypatch.setattr(publishing, "ENV_PATH", tmp_path / ".env")
    for cfg in publishing.PLATFORM_CONFIGS.values():
        for f in cfg.fields:
            monkeypatch.delenv(f.env_key, raising=False)


def test_not_configured_by_default():
    for platform in publishing.PLATFORM_CONFIGS:
        assert publishing.is_configured(platform) is False


def test_save_and_clear_credentials(monkeypatch):
    publishing.save_credentials("youtube", {
        "YOUTUBE_CLIENT_ID": "id", "YOUTUBE_CLIENT_SECRET": "secret", "YOUTUBE_REFRESH_TOKEN": "token",
    })
    assert publishing.is_configured("youtube") is True

    publishing.clear_credentials("youtube")
    assert publishing.is_configured("youtube") is False


def test_save_credentials_rejects_unknown_field():
    with pytest.raises(ValueError):
        publishing.save_credentials("youtube", {"KHONG_HOP_LE": "x"})


def test_publish_returns_clear_error_when_not_configured(tmp_path):
    fake_video = tmp_path / "v.mp4"
    fake_video.write_bytes(b"fake")
    result = publishing.publish_youtube(fake_video, "Tieu de", "Mo ta", ["#a"])
    assert result.success is False
    assert "Chưa cấu hình" in result.error


def _fake_response(json_data, status=200):
    request = httpx.Request("POST", "https://example.com")
    return httpx.Response(status, request=request, content=json.dumps(json_data).encode())


def test_publish_youtube_success(monkeypatch, tmp_path):
    publishing.save_credentials("youtube", {
        "YOUTUBE_CLIENT_ID": "id", "YOUTUBE_CLIENT_SECRET": "secret", "YOUTUBE_REFRESH_TOKEN": "token",
    })
    fake_video = tmp_path / "v.mp4"
    fake_video.write_bytes(b"fake video bytes")

    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        if "oauth2.googleapis.com" in url:
            return _fake_response({"access_token": "fake-access-token"})
        return _fake_response({"id": "abc123"})

    monkeypatch.setattr(publishing.httpx, "post", fake_post)

    result = publishing.publish_youtube(fake_video, "Tiêu đề", "Mô tả", ["#lichsu"])
    assert result.success is True
    assert result.post_url == "https://youtu.be/abc123"
    assert calls[0][0] == "https://oauth2.googleapis.com/token"
    assert "googleapis.com/upload/youtube" in calls[1][0]


def test_publish_facebook_success(monkeypatch, tmp_path):
    publishing.save_credentials("facebook", {
        "FACEBOOK_PAGE_ID": "page1", "FACEBOOK_PAGE_ACCESS_TOKEN": "tok",
    })
    fake_video = tmp_path / "v.mp4"
    fake_video.write_bytes(b"fake")

    def fake_post(url, **kwargs):
        assert "page1" in url
        return _fake_response({"id": "vid123"})

    monkeypatch.setattr(publishing.httpx, "post", fake_post)
    result = publishing.publish_facebook(fake_video, "T", "D", [])
    assert result.success is True
    assert "vid123" in result.post_url


def test_publish_handles_http_error_gracefully(monkeypatch, tmp_path):
    publishing.save_credentials("facebook", {
        "FACEBOOK_PAGE_ID": "page1", "FACEBOOK_PAGE_ACCESS_TOKEN": "tok",
    })
    fake_video = tmp_path / "v.mp4"
    fake_video.write_bytes(b"fake")

    def fake_post(url, **kwargs):
        return _fake_response({"error": "bad token"}, status=401)

    monkeypatch.setattr(publishing.httpx, "post", fake_post)
    result = publishing.publish_facebook(fake_video, "T", "D", [])
    assert result.success is False
    assert result.error is not None
