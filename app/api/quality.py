"""Bước 11-12 (Mục 3, V3) qua API — chấm điểm kịch bản (đúng 8 tiêu chí bản
gốc) + tự sinh 10 tiêu đề/5 thumbnail/3 mô tả/5 CTA để chọn. Xem
app/services/quality_review.py."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.quality_review import SUPPORTED_PLATFORMS, generate_metadata, generate_seo_metadata, score_script

router = APIRouter()


class ScriptTextInput(BaseModel):
    script_text: str = Field(..., min_length=1)


class SeoInput(BaseModel):
    script_text: str = Field(..., min_length=1)
    platform: str = Field(..., description=f"1 trong: {SUPPORTED_PLATFORMS}")


@router.post("/quality/score")
def post_score_script(payload: ScriptTextInput):
    result = score_script(payload.script_text)
    return {
        "criteria": [{"key": c.key, "score": c.score, "comment": c.comment} for c in result.criteria],
        "total_score": result.total_score,
        "summary": result.summary,
    }


@router.post("/quality/metadata")
def post_generate_metadata(payload: ScriptTextInput):
    m = generate_metadata(payload.script_text)
    return {
        "titles": m.titles,
        "subtitle": m.subtitle,
        "descriptions": m.descriptions,
        "cta_texts": m.cta_texts,
        "thumbnail_texts": m.thumbnail_texts,
    }


@router.post("/quality/seo")
def post_generate_seo(payload: SeoInput):
    if payload.platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(400, f"platform phải là 1 trong {SUPPORTED_PLATFORMS}")
    m = generate_seo_metadata(payload.script_text, payload.platform)
    return {
        "platform": m.platform,
        "title": m.title,
        "caption_or_description": m.caption_or_description,
        "hashtags": m.hashtags,
        "tip": m.tip,
    }
