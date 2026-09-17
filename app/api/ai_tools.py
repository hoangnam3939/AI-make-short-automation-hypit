"""Bước 9 (Mục 3/7, V3) qua API — danh sách AI làm video ngoài + máy tính
ngân sách. App KHÔNG tự tạo video, chỉ đưa link + ước tính chi phí."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.ai_tools import AI_TOOLS, estimate_budget, get_recommended_tools

router = APIRouter()


@router.get("/ai-tools")
def list_ai_tools(recommended_only: bool = False):
    tools = get_recommended_tools() if recommended_only else AI_TOOLS
    return {"tools": [asdict(t) for t in tools]}


class BudgetInput(BaseModel):
    tool_id: str
    video_seconds: int = Field(..., gt=0)
    retry_buffer_pct: int = Field(40, ge=0, le=100)


@router.post("/ai-tools/budget")
def budget(payload: BudgetInput):
    try:
        return estimate_budget(payload.tool_id, payload.video_seconds, payload.retry_buffer_pct)
    except ValueError as e:
        raise HTTPException(404, str(e))
