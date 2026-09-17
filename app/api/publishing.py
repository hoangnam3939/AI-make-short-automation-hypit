"""API cho việc lưu API key/token + đăng video lên nhiều nền tảng mạng xã
hội (xem cảnh báo CHƯA TEST THẬT ở đầu app/services/publishing.py)."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import publishing
from app.services.production_pipeline import get_job

router = APIRouter()


@router.get("/publishing/status")
def get_publishing_status():
    return {
        platform: {
            "display_name": cfg.display_name,
            "configured": publishing.is_configured(platform),
            "requires_public_video_url": cfg.requires_public_video_url,
            "fields": [{"env_key": f.env_key, "label": f.label} for f in cfg.fields],
        }
        for platform, cfg in publishing.PLATFORM_CONFIGS.items()
    }


class SaveCredentialsInput(BaseModel):
    values: dict[str, str] = Field(..., description="env_key -> giá trị, xem GET /publishing/status để biết field")


@router.post("/publishing/settings/{platform}")
def save_platform_credentials(platform: str, payload: SaveCredentialsInput):
    if platform not in publishing.PLATFORM_CONFIGS:
        raise HTTPException(400, f"Nền tảng không hợp lệ: {platform}")
    try:
        publishing.save_credentials(platform, payload.values)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"platform": platform, "configured": publishing.is_configured(platform)}


@router.delete("/publishing/settings/{platform}")
def clear_platform_credentials(platform: str):
    if platform not in publishing.PLATFORM_CONFIGS:
        raise HTTPException(400, f"Nền tảng không hợp lệ: {platform}")
    publishing.clear_credentials(platform)
    return {"platform": platform, "configured": False}


class PublishInput(BaseModel):
    platform: str
    job_id: str
    language_code: str
    title: str = ""
    description: str = ""
    hashtags: list[str] = []
    video_url: str | None = Field(
        None, description="BẮT BUỘC cho instagram/threads — video phải ở URL công khai, xem publishing.py"
    )


@router.post("/publishing/publish")
def publish_video(payload: PublishInput):
    if payload.platform not in publishing.PLATFORM_CONFIGS:
        raise HTTPException(400, f"Nền tảng không hợp lệ: {payload.platform}")

    job = get_job(payload.job_id)
    if job is None:
        raise HTTPException(404, "Không tìm thấy job này (có thể server đã khởi động lại).")
    lang_result = job.languages.get(payload.language_code)
    if lang_result is None or lang_result.status != "done" or not lang_result.final_video_path:
        raise HTTPException(409, "Video ngôn ngữ này chưa dựng xong.")
    video_path = Path(lang_result.final_video_path)

    cfg = publishing.PLATFORM_CONFIGS[payload.platform]
    if cfg.requires_public_video_url and not payload.video_url:
        raise HTTPException(
            400,
            f"{cfg.display_name} bắt buộc video phải có sẵn ở 1 URL công khai "
            "(app chạy local, chưa tự host được) — tự host video ở đâu đó rồi dán URL vào `video_url`.",
        )

    if payload.platform == "youtube":
        result = publishing.publish_youtube(video_path, payload.title, payload.description, payload.hashtags)
    elif payload.platform == "facebook":
        result = publishing.publish_facebook(video_path, payload.title, payload.description, payload.hashtags)
    elif payload.platform == "instagram":
        result = publishing.publish_instagram(payload.video_url, payload.description, payload.hashtags)
    elif payload.platform == "tiktok":
        result = publishing.publish_tiktok(video_path, payload.title, payload.hashtags)
    elif payload.platform == "threads":
        result = publishing.publish_threads(payload.video_url, payload.description)
    elif payload.platform == "twitter_x":
        result = publishing.publish_twitter_x(video_path, payload.description, payload.hashtags)
    elif payload.platform == "zalo":
        result = publishing.publish_zalo(video_path, payload.description)
    else:
        raise HTTPException(400, f"Chưa hỗ trợ đăng bài cho nền tảng: {payload.platform}")

    return {
        "platform": result.platform, "success": result.success,
        "post_url": result.post_url, "error": result.error,
    }
