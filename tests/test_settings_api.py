import os

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import llm


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Cô lập hoàn toàn khỏi trạng thái LLM thật của máy đang chạy test (kể
    cả LLM_BACKEND đã lưu và các CLI đã cài sẵn) — nếu không, máy nào đã
    cấu hình sẵn 1 trong 4 cách (như máy dev này có Claude CLI) sẽ khiến
    test "chưa cấu hình gì" sai theo, đúng lỗi thật đã biết trước đây."""
    monkeypatch.setattr(llm, "ENV_PATH", tmp_path / ".env")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BACKEND", raising=False)
    monkeypatch.setattr(llm, "claude_cli_available", lambda: False)
    monkeypatch.setattr(llm, "codex_cli_available", lambda: False)
    monkeypatch.setattr(llm, "gemini_cli_available", lambda: False)
    return TestClient(app)


def test_get_settings_not_configured_initially(client):
    res = client.get("/api/settings")
    assert res.status_code == 200
    assert res.json()["llm_configured"] is False


def test_set_api_key_then_configured(client):
    res = client.post("/api/settings/api-key", json={"api_key": "sk-ant-fake-123"})
    assert res.status_code == 200
    assert res.json() == {"llm_configured": True}

    res = client.get("/api/settings")
    assert res.json()["llm_configured"] is True


def test_set_api_key_response_never_echoes_key(client):
    res = client.post("/api/settings/api-key", json={"api_key": "sk-ant-super-secret"})
    assert "sk-ant-super-secret" not in res.text


def test_set_empty_api_key_rejected(client):
    res = client.post("/api/settings/api-key", json={"api_key": ""})
    assert res.status_code == 422  # Pydantic min_length=1


def test_delete_api_key(client):
    client.post("/api/settings/api-key", json={"api_key": "sk-ant-fake-123"})
    res = client.delete("/api/settings/api-key")
    assert res.status_code == 200
    assert res.json() == {"llm_configured": False}


def test_get_settings_includes_all_4_backend_fields(client):
    res = client.get("/api/settings")
    data = res.json()
    assert set(data) == {
        "llm_configured", "llm_backend", "claude_cli_available",
        "codex_cli_available", "gemini_cli_available",
        "anthropic_api_configured", "openai_api_configured", "gemini_api_configured",
    }
    assert data["llm_backend"] == "api"


@pytest.mark.parametrize("backend,env_var", [
    ("api", "ANTHROPIC_API_KEY"),
    ("openai_api", "OPENAI_API_KEY"),
    ("gemini_api", "GEMINI_API_KEY"),
])
def test_set_api_key_per_backend_persists_to_correct_env_var(client, backend, env_var, monkeypatch):
    monkeypatch.delenv(env_var, raising=False)
    res = client.post("/api/settings/api-key", json={"api_key": "fake-key-123", "backend": backend})
    assert res.status_code == 200
    assert res.json() == {"llm_configured": backend == "api"}
    assert os.environ.get(env_var) == "fake-key-123"


def test_set_api_key_unknown_backend_rejected(client):
    res = client.post("/api/settings/api-key", json={"api_key": "fake-key", "backend": "bard"})
    assert res.status_code == 400


def test_delete_api_key_per_backend(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client.post("/api/settings/api-key", json={"api_key": "fake-key", "backend": "openai_api"})
    assert os.environ.get("OPENAI_API_KEY") == "fake-key"
    res = client.delete("/api/settings/api-key", params={"backend": "openai_api"})
    assert res.status_code == 200
    assert os.environ.get("OPENAI_API_KEY") is None


@pytest.mark.parametrize("backend", ["claude_cli", "codex_cli", "gemini_cli"])
def test_set_llm_backend_accepts_every_cli_backend(client, backend):
    res = client.post("/api/settings/llm-backend", json={"backend": backend})
    assert res.status_code == 200
    assert res.json()["llm_backend"] == backend

    res = client.get("/api/settings")
    assert res.json()["llm_backend"] == backend


def test_set_llm_backend_rejects_unknown_value(client):
    res = client.post("/api/settings/llm-backend", json={"backend": "bard"})
    assert res.status_code == 400


def test_set_llm_backend_reports_configured_when_cli_available(client, monkeypatch):
    monkeypatch.setattr(llm, "codex_cli_available", lambda: True)
    res = client.post("/api/settings/llm-backend", json={"backend": "codex_cli"})
    assert res.status_code == 200
    body = res.json()
    assert body["llm_configured"] is True
    assert body["codex_cli_available"] is True
