"""Bước 12 mở rộng (2026-09-14) — đăng video hoàn chỉnh lên nhiều nền tảng
mạng xã hội trực tiếp từ app, dùng nội dung SEO đã sinh riêng cho từng nơi
(`quality_review.py::generate_seo_metadata`). Người dùng có thể chọn NHIỀU
nền tảng cùng lúc cho 1 video, app tự đăng lần lượt lên từng nơi đã chọn.

⚠️ CẢNH BÁO QUAN TRỌNG (đọc trước khi dùng thật): các hàm `publish_*` dưới
đây viết dựa theo tài liệu API CHÍNH THỨC công khai của từng nền tảng,
nhưng CHƯA ĐƯỢC KIỂM THỬ VỚI TÀI KHOẢN THẬT — khác với MỌI phần khác của
app trong README (đều đã chạy thật ít nhất 1 lần trước khi coi là xong).
Lý do: tại thời điểm viết (2026-09-14) người dùng CHƯA có API key/token cho
bất kỳ nền tảng nào. PHẢI tự thử lại cẩn thận với 1 video test nhỏ trên
từng nền tảng trước khi tin dùng cho video thật, và báo lại lỗi cụ thể nếu
gặp để sửa tiếp — xem thêm ghi chú riêng ở từng hàm bên dưới.

Cách lấy "chìa khoá" (API key/token) cho từng nền tảng — người dùng tự làm,
Claude/app KHÔNG được tự tạo tài khoản/đăng nhập thay:
- YouTube: vào Google Cloud Console, tạo project, bật "YouTube Data API
  v3", tạo OAuth Client ID (loại "Desktop app"), rồi lấy refresh token qua
  luồng OAuth 2.0 (VD dùng OAuth 2.0 Playground của Google).
- Facebook: vào Meta for Developers, tạo App, thêm sản phẩm "Facebook
  Login", lấy Page Access Token (loại "never expire" qua Graph API
  Explorer) cho đúng Trang (Page) muốn đăng.
- Instagram: CẦN Instagram Business/Creator Account đã liên kết với 1
  Facebook Page, lấy Instagram Business Account ID qua Graph API. LƯU Ý
  QUAN TRỌNG: Instagram Content Publishing API bắt buộc video phải có sẵn
  ở 1 URL CÔNG KHAI (Instagram tự tải về từ URL đó) — KHÔNG hỗ trợ tải file
  trực tiếp từ máy tính như Facebook/YouTube/TikTok/Twitter. App hiện chạy
  local nên chưa có chỗ host URL công khai cho video — cần người dùng tự
  host video ở đâu đó (VD Google Drive public link, S3...) rồi dán URL vào.
- TikTok: vào TikTok for Developers, tạo app, xin cấp quyền
  "video.publish" (Content Posting API) — CẦN TikTok DUYỆT app trước khi
  dùng được với tài khoản thật, không chỉ đăng ký là dùng ngay được.
- Threads: qua Meta for Developers (chung hệ sinh thái Facebook), dùng
  Threads API — CÙNG hạn chế như Instagram: cần video ở URL công khai.
- Twitter/X: vào X Developer Portal — LƯU Ý: đăng bài kèm media qua API
  hiện yêu cầu gói trả phí (từ gói "Basic" trở lên, không dùng được ở gói
  Free) tính đến thời điểm viết.
- Zalo: vào Zalo for Developers, tạo Official Account (OA) app, xin quyền
  đăng bài (Feed/Article) — API Zalo OA ít tài liệu công khai bằng các nền
  tảng trên, nhiều khả năng cần điều chỉnh thêm khi thử thật.

Lưu API key/token vào file `.env` (không commit git) qua `save_credential()`
— giống hệt cách `app/services/llm.py` lưu ANTHROPIC_API_KEY.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import httpx
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(ENV_PATH)


def _write_env_line(key: str, value: str | None) -> None:
    """Y hệt logic đã chứng minh ở `app/services/llm.py::_write_env_line`
    — tách riêng ở đây để `publishing.py` không phụ thuộc chéo vào module
    llm.py (2 việc không liên quan nhau), đổi lại là trùng ~10 dòng logic
    đơn giản (đúng mức chấp nhận được, xem `_probe_duration` cũng đang lặp
    lại tương tự ở vài file khác trong dự án)."""
    lines: list[str] = []
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if not line.startswith(f"{key}="):
                lines.append(line)
    if value is not None:
        lines.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    if value is not None:
        os.environ[key] = value
    else:
        os.environ.pop(key, None)


@dataclass
class PublishResult:
    platform: str
    success: bool
    post_url: str | None = None
    error: str | None = None


@dataclass
class PlatformField:
    """1 ô nhập trong màn hình Cài đặt cho 1 nền tảng (VD "Page Access
    Token")."""

    env_key: str
    label: str


@dataclass
class PlatformConfig:
    platform: str
    display_name: str
    fields: list[PlatformField]
    requires_public_video_url: bool = False  # Instagram/Threads: không nhận upload file trực tiếp


PLATFORM_CONFIGS: dict[str, PlatformConfig] = {
    "youtube": PlatformConfig(
        platform="youtube", display_name="YouTube",
        fields=[
            PlatformField("YOUTUBE_CLIENT_ID", "Client ID"),
            PlatformField("YOUTUBE_CLIENT_SECRET", "Client Secret"),
            PlatformField("YOUTUBE_REFRESH_TOKEN", "Refresh Token"),
        ],
    ),
    "facebook": PlatformConfig(
        platform="facebook", display_name="Facebook",
        fields=[
            PlatformField("FACEBOOK_PAGE_ID", "Page ID"),
            PlatformField("FACEBOOK_PAGE_ACCESS_TOKEN", "Page Access Token"),
        ],
    ),
    "instagram": PlatformConfig(
        platform="instagram", display_name="Instagram",
        fields=[
            PlatformField("INSTAGRAM_BUSINESS_ACCOUNT_ID", "Instagram Business Account ID"),
            PlatformField("INSTAGRAM_ACCESS_TOKEN", "Access Token"),
        ],
        requires_public_video_url=True,
    ),
    "tiktok": PlatformConfig(
        platform="tiktok", display_name="TikTok",
        fields=[PlatformField("TIKTOK_ACCESS_TOKEN", "Access Token")],
    ),
    "threads": PlatformConfig(
        platform="threads", display_name="Threads",
        fields=[
            PlatformField("THREADS_USER_ID", "Threads User ID"),
            PlatformField("THREADS_ACCESS_TOKEN", "Access Token"),
        ],
        requires_public_video_url=True,
    ),
    "twitter_x": PlatformConfig(
        platform="twitter_x", display_name="Twitter/X",
        fields=[
            PlatformField("TWITTER_CONSUMER_KEY", "API Key (Consumer Key)"),
            PlatformField("TWITTER_CONSUMER_SECRET", "API Secret (Consumer Secret)"),
            PlatformField("TWITTER_ACCESS_TOKEN", "Access Token"),
            PlatformField("TWITTER_ACCESS_TOKEN_SECRET", "Access Token Secret"),
        ],
    ),
    "zalo": PlatformConfig(
        platform="zalo", display_name="Zalo",
        fields=[
            PlatformField("ZALO_OA_ID", "Official Account ID"),
            PlatformField("ZALO_OA_ACCESS_TOKEN", "Access Token"),
        ],
    ),
}


def is_configured(platform: str) -> bool:
    config = PLATFORM_CONFIGS.get(platform)
    if config is None:
        return False
    return all(os.environ.get(f.env_key) for f in config.fields)


def save_credentials(platform: str, values: dict[str, str]) -> None:
    config = PLATFORM_CONFIGS.get(platform)
    if config is None:
        raise ValueError(f"Nền tảng không hợp lệ: {platform}")
    valid_keys = {f.env_key for f in config.fields}
    for key, value in values.items():
        if key not in valid_keys:
            raise ValueError(f"'{key}' không phải trường hợp lệ của {platform}")
        _write_env_line(key, value.strip() or None)


def clear_credentials(platform: str) -> None:
    config = PLATFORM_CONFIGS.get(platform)
    if config is None:
        raise ValueError(f"Nền tảng không hợp lệ: {platform}")
    for f in config.fields:
        _write_env_line(f.env_key, None)


def _not_configured_result(platform: str) -> PublishResult:
    return PublishResult(
        platform=platform, success=False,
        error=f"Chưa cấu hình API key/token cho {PLATFORM_CONFIGS[platform].display_name}. "
              "Vào màn hình Cài đặt để nhập trước.",
    )


# ---------------------------------------------------------------------------
# YouTube — Data API v3, resumable/simple upload qua OAuth2 refresh token.
# CHƯA TEST THẬT (chưa có API key tại thời điểm viết).
# ---------------------------------------------------------------------------

def _youtube_access_token() -> str:
    resp = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": os.environ["YOUTUBE_CLIENT_ID"],
            "client_secret": os.environ["YOUTUBE_CLIENT_SECRET"],
            "refresh_token": os.environ["YOUTUBE_REFRESH_TOKEN"],
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def publish_youtube(video_path: Path, title: str, description: str, hashtags: list[str]) -> PublishResult:
    if not is_configured("youtube"):
        return _not_configured_result("youtube")
    try:
        access_token = _youtube_access_token()
        tags = [h.lstrip("#") for h in hashtags]
        metadata = {
            "snippet": {"title": title[:100], "description": description, "tags": tags},
            "status": {"privacyStatus": "private"},  # an toàn mặc định: KHÔNG tự công khai video
        }
        with open(video_path, "rb") as f:
            resp = httpx.post(
                "https://www.googleapis.com/upload/youtube/v3/videos",
                params={"uploadType": "multipart", "part": "snippet,status"},
                headers={"Authorization": f"Bearer {access_token}"},
                files={
                    "metadata": (None, __import__("json").dumps(metadata), "application/json"),
                    "video": (video_path.name, f, "video/mp4"),
                },
                timeout=600,
            )
        resp.raise_for_status()
        video_id = resp.json()["id"]
        return PublishResult(platform="youtube", success=True, post_url=f"https://youtu.be/{video_id}")
    except Exception as exc:  # noqa: BLE001 - lỗi đăng 1 nền tảng không nên làm crash cả app
        return PublishResult(platform="youtube", success=False, error=str(exc))


# ---------------------------------------------------------------------------
# Facebook — Graph API, đăng video trực tiếp lên Page qua /{page-id}/videos.
# CHƯA TEST THẬT.
# ---------------------------------------------------------------------------

def publish_facebook(video_path: Path, title: str, description: str, hashtags: list[str]) -> PublishResult:
    if not is_configured("facebook"):
        return _not_configured_result("facebook")
    try:
        page_id = os.environ["FACEBOOK_PAGE_ID"]
        token = os.environ["FACEBOOK_PAGE_ACCESS_TOKEN"]
        full_description = description + ("\n\n" + " ".join(hashtags) if hashtags else "")
        with open(video_path, "rb") as f:
            resp = httpx.post(
                f"https://graph-video.facebook.com/v19.0/{page_id}/videos",
                params={"access_token": token, "title": title, "description": full_description},
                files={"source": (video_path.name, f, "video/mp4")},
                timeout=600,
            )
        resp.raise_for_status()
        video_id = resp.json()["id"]
        return PublishResult(platform="facebook", success=True, post_url=f"https://www.facebook.com/{video_id}")
    except Exception as exc:  # noqa: BLE001
        return PublishResult(platform="facebook", success=False, error=str(exc))


# ---------------------------------------------------------------------------
# Instagram — Content Publishing API, BẮT BUỘC video_url công khai (không
# nhận upload file trực tiếp) — xem cảnh báo ở đầu file. CHƯA TEST THẬT.
# ---------------------------------------------------------------------------

def publish_instagram(video_url: str, caption: str, hashtags: list[str]) -> PublishResult:
    """Khác các hàm publish_* khác: nhận `video_url` (URL công khai) thay vì
    đường dẫn file cục bộ, vì Instagram API không hỗ trợ tải file trực tiếp
    (xem cảnh báo đầu file)."""
    if not is_configured("instagram"):
        return _not_configured_result("instagram")
    try:
        ig_id = os.environ["INSTAGRAM_BUSINESS_ACCOUNT_ID"]
        token = os.environ["INSTAGRAM_ACCESS_TOKEN"]
        full_caption = caption + ("\n\n" + " ".join(hashtags) if hashtags else "")
        create_resp = httpx.post(
            f"https://graph.facebook.com/v19.0/{ig_id}/media",
            data={"media_type": "REELS", "video_url": video_url, "caption": full_caption, "access_token": token},
            timeout=60,
        )
        create_resp.raise_for_status()
        container_id = create_resp.json()["id"]
        publish_resp = httpx.post(
            f"https://graph.facebook.com/v19.0/{ig_id}/media_publish",
            data={"creation_id": container_id, "access_token": token},
            timeout=60,
        )
        publish_resp.raise_for_status()
        media_id = publish_resp.json()["id"]
        return PublishResult(platform="instagram", success=True, post_url=f"https://www.instagram.com/reel/{media_id}")
    except Exception as exc:  # noqa: BLE001
        return PublishResult(platform="instagram", success=False, error=str(exc))


# ---------------------------------------------------------------------------
# TikTok — Content Posting API v2, chế độ FILE_UPLOAD (tải file trực tiếp).
# CẦN app đã được TikTok duyệt quyền "video.publish". CHƯA TEST THẬT.
# ---------------------------------------------------------------------------

def publish_tiktok(video_path: Path, title: str, hashtags: list[str]) -> PublishResult:
    if not is_configured("tiktok"):
        return _not_configured_result("tiktok")
    try:
        token = os.environ["TIKTOK_ACCESS_TOKEN"]
        video_size = video_path.stat().st_size
        init_resp = httpx.post(
            "https://open.tiktokapis.com/v2/post/publish/video/init/",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "post_info": {
                    "title": (title + " " + " ".join(hashtags)).strip(),
                    "privacy_level": "SELF_ONLY",  # an toàn mặc định: KHÔNG tự công khai video
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": video_size,
                    "chunk_size": video_size,
                    "total_chunk_count": 1,
                },
            },
            timeout=60,
        )
        init_resp.raise_for_status()
        init_data = init_resp.json()["data"]
        upload_url = init_data["upload_url"]
        publish_id = init_data["publish_id"]
        with open(video_path, "rb") as f:
            upload_resp = httpx.put(
                upload_url,
                content=f.read(),
                headers={"Content-Range": f"bytes 0-{video_size - 1}/{video_size}", "Content-Type": "video/mp4"},
                timeout=600,
            )
        upload_resp.raise_for_status()
        return PublishResult(platform="tiktok", success=True, post_url=f"publish_id:{publish_id}")
    except Exception as exc:  # noqa: BLE001
        return PublishResult(platform="tiktok", success=False, error=str(exc))


# ---------------------------------------------------------------------------
# Threads — Threads API (Meta), BẮT BUỘC video_url công khai. CHƯA TEST THẬT.
# ---------------------------------------------------------------------------

def publish_threads(video_url: str, text: str) -> PublishResult:
    if not is_configured("threads"):
        return _not_configured_result("threads")
    try:
        user_id = os.environ["THREADS_USER_ID"]
        token = os.environ["THREADS_ACCESS_TOKEN"]
        create_resp = httpx.post(
            f"https://graph.threads.net/v1.0/{user_id}/threads",
            data={"media_type": "VIDEO", "video_url": video_url, "text": text, "access_token": token},
            timeout=60,
        )
        create_resp.raise_for_status()
        container_id = create_resp.json()["id"]
        publish_resp = httpx.post(
            f"https://graph.threads.net/v1.0/{user_id}/threads_publish",
            data={"creation_id": container_id, "access_token": token},
            timeout=60,
        )
        publish_resp.raise_for_status()
        post_id = publish_resp.json()["id"]
        return PublishResult(platform="threads", success=True, post_url=f"https://www.threads.net/post/{post_id}")
    except Exception as exc:  # noqa: BLE001
        return PublishResult(platform="threads", success=False, error=str(exc))


# ---------------------------------------------------------------------------
# Twitter/X — media upload (chunked) + tạo bài đăng. CẦN gói API trả phí
# (từ "Basic" trở lên) để đăng bài qua API. CHƯA TEST THẬT.
# ---------------------------------------------------------------------------

def publish_twitter_x(video_path: Path, text: str, hashtags: list[str]) -> PublishResult:
    if not is_configured("twitter_x"):
        return _not_configured_result("twitter_x")
    try:
        from requests_oauthlib import OAuth1  # dùng OAuth1 cho media upload (bắt buộc theo API Twitter)

        auth = OAuth1(
            os.environ["TWITTER_CONSUMER_KEY"], os.environ["TWITTER_CONSUMER_SECRET"],
            os.environ["TWITTER_ACCESS_TOKEN"], os.environ["TWITTER_ACCESS_TOKEN_SECRET"],
        )
        video_bytes = video_path.read_bytes()
        init_resp = httpx.post(
            "https://upload.twitter.com/1.1/media/upload.json",
            data={"command": "INIT", "total_bytes": len(video_bytes), "media_type": "video/mp4",
                  "media_category": "tweet_video"},
            auth=auth, timeout=60,
        )
        init_resp.raise_for_status()
        media_id = init_resp.json()["media_id_string"]
        append_resp = httpx.post(
            "https://upload.twitter.com/1.1/media/upload.json",
            data={"command": "APPEND", "media_id": media_id, "segment_index": 0},
            files={"media": video_bytes}, auth=auth, timeout=300,
        )
        append_resp.raise_for_status()
        finalize_resp = httpx.post(
            "https://upload.twitter.com/1.1/media/upload.json",
            data={"command": "FINALIZE", "media_id": media_id}, auth=auth, timeout=60,
        )
        finalize_resp.raise_for_status()

        full_text = (text + " " + " ".join(hashtags)).strip()[:280]
        tweet_resp = httpx.post(
            "https://api.twitter.com/2/tweets",
            json={"text": full_text, "media": {"media_ids": [media_id]}},
            auth=auth, timeout=60,
        )
        tweet_resp.raise_for_status()
        tweet_id = tweet_resp.json()["data"]["id"]
        return PublishResult(platform="twitter_x", success=True, post_url=f"https://x.com/i/status/{tweet_id}")
    except Exception as exc:  # noqa: BLE001
        return PublishResult(platform="twitter_x", success=False, error=str(exc))


# ---------------------------------------------------------------------------
# Zalo OA — API ít tài liệu công khai hơn các nền tảng trên, nhiều khả năng
# cần điều chỉnh khi thử thật. CHƯA TEST THẬT.
# ---------------------------------------------------------------------------

def publish_zalo(video_path: Path, text: str) -> PublishResult:
    if not is_configured("zalo"):
        return _not_configured_result("zalo")
    try:
        token = os.environ["ZALO_OA_ACCESS_TOKEN"]
        with open(video_path, "rb") as f:
            upload_resp = httpx.post(
                "https://openapi.zalo.me/v2.0/oa/upload/video",
                headers={"access_token": token},
                files={"file": (video_path.name, f, "video/mp4")},
                data={"video_name": video_path.stem},
                timeout=600,
            )
        upload_resp.raise_for_status()
        video_token = upload_resp.json()["data"]["token"]
        post_resp = httpx.post(
            "https://openapi.zalo.me/v2.0/oa/article",
            headers={"access_token": token, "Content-Type": "application/json"},
            json={"video": {"token": video_token}, "body": text},
            timeout=60,
        )
        post_resp.raise_for_status()
        article_id = post_resp.json().get("data", {}).get("article_id", "")
        return PublishResult(platform="zalo", success=True, post_url=f"zalo_article:{article_id}")
    except Exception as exc:  # noqa: BLE001
        return PublishResult(platform="zalo", success=False, error=str(exc))
