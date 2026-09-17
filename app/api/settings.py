"""Cài đặt — nơi người dùng chọn cách gọi LLM (API key Anthropic riêng, hoặc
1 trong 3 tài khoản CLI đã đăng nhập sẵn: Claude Pro/Max, ChatGPT Plus/Pro,
Gemini) và nhập API key nếu chọn cách đó.

Key lưu cục bộ ở file .env (không commit git), KHÔNG BAO GIỜ trả lại cho
frontend sau khi lưu — chỉ trả trạng thái configured=true/false.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import llm

router = APIRouter()


class ApiKeyInput(BaseModel):
    api_key: str = Field(..., min_length=1)
    # "api" (Anthropic, mặc định — giữ tương thích ngược với client cũ chưa
    # gửi field này) | "openai_api" | "gemini_api". Xem llm.API_KEY_ENV_VARS.
    backend: str = Field(default="api")


class LlmBackendInput(BaseModel):
    backend: str = Field(..., min_length=1)


def _settings_dict() -> dict:
    return {
        "llm_configured": llm.is_configured(),
        "llm_backend": llm.get_backend(),
        "claude_cli_available": llm.claude_cli_available(),
        "codex_cli_available": llm.codex_cli_available(),
        "gemini_cli_available": llm.gemini_cli_available(),
        # Trạng thái RIÊNG từng loại API key (2026-09-17) — khác với
        # "llm_configured" (chỉ phản ánh backend đang ACTIVE) — cần thiết để
        # menu xổ xuống "Dùng API key riêng" hiện đúng ✅/⬜ cho từng hãng dù
        # hãng đó có đang được chọn làm backend hiện hành hay không.
        "anthropic_api_configured": llm.has_api_key("api"),
        "openai_api_configured": llm.has_api_key("openai_api"),
        "gemini_api_configured": llm.has_api_key("gemini_api"),
    }


@router.get("/settings")
def get_settings():
    return _settings_dict()


@router.post("/settings/llm-backend")
def set_llm_backend(payload: LlmBackendInput):
    try:
        llm.save_backend(payload.backend)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _settings_dict()


@router.post("/settings/api-key")
def set_api_key(payload: ApiKeyInput):
    try:
        llm.save_api_key(payload.api_key, backend=payload.backend)
    except ValueError as e:
        raise HTTPException(400, str(e))
    # is_configured() (không hardcode True): phản ánh ĐÚNG backend đang
    # active — lưu key OpenAI trong khi backend active vẫn là Anthropic thì
    # "llm_configured" KHÔNG được báo true nếu Anthropic chưa có key.
    return {"llm_configured": llm.is_configured()}


@router.delete("/settings/api-key")
def delete_api_key(backend: str = "api"):
    try:
        llm.clear_api_key(backend=backend)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"llm_configured": llm.is_configured()}
