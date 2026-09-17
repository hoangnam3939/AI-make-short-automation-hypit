"""Test API cho Bước 3 (/story/theme) và Bước 4 (/story/hooks) — mock
script_writer, không cần API key thật (xem tests/test_script_writer.py cho
test logic lắp ráp prompt)."""
from fastapi.testclient import TestClient

from app.api import story as story_api
from app.main import app
from app.services.llm import LlmNotConfiguredError
from app.services.script_writer import HookCandidate, HookResult, ScriptResult, ThemeAndGoals

client = TestClient(app)


def test_theme_endpoint_returns_4_fields(monkeypatch):
    fake = ThemeAndGoals(
        target_audience="Người trẻ yêu lịch sử",
        audience_pain_point="Thấy sử khô khan",
        core_message="Sử Việt hào hùng",
        best_angle="Góc nhìn binh sĩ",
    )
    monkeypatch.setattr(story_api.script_writer, "determine_theme_and_goals", lambda story: fake)
    res = client.post("/api/story/theme", json={"story": "Câu chuyện mẫu."})
    assert res.status_code == 200
    assert res.json() == {
        "target_audience": "Người trẻ yêu lịch sử",
        "audience_pain_point": "Thấy sử khô khan",
        "core_message": "Sử Việt hào hùng",
        "best_angle": "Góc nhìn binh sĩ",
    }


def test_theme_endpoint_rejects_empty_story():
    res = client.post("/api/story/theme", json={"story": ""})
    assert res.status_code == 422


def test_theme_endpoint_returns_400_when_llm_not_configured(monkeypatch):
    def raise_not_configured(story):
        raise LlmNotConfiguredError("Chưa cấu hình API key.")

    monkeypatch.setattr(story_api.script_writer, "determine_theme_and_goals", raise_not_configured)
    res = client.post("/api/story/theme", json={"story": "Câu chuyện mẫu."})
    assert res.status_code == 400


def test_hooks_endpoint_returns_candidates_and_top3(monkeypatch):
    fake = HookResult(
        candidates=[HookCandidate(group="to_mo", text="Điều gì đã xảy ra?")],
        top_3=["Điều gì đã xảy ra?"],
    )
    monkeypatch.setattr(story_api.script_writer, "generate_hooks", lambda story, theme: fake)
    res = client.post("/api/story/hooks", json={"story": "Câu chuyện mẫu."})
    assert res.status_code == 200
    data = res.json()
    assert data["candidates"] == [{"group": "to_mo", "text": "Điều gì đã xảy ra?"}]
    assert data["top_3"] == ["Điều gì đã xảy ra?"]


def test_hooks_endpoint_passes_theme_through(monkeypatch):
    captured = {}

    def fake_generate_hooks(story, theme):
        captured["theme"] = theme
        return HookResult()

    monkeypatch.setattr(story_api.script_writer, "generate_hooks", fake_generate_hooks)
    res = client.post(
        "/api/story/hooks",
        json={"story": "Câu chuyện mẫu.", "theme": {"target_audience": "Học sinh cấp 2", "core_message": "", "audience_pain_point": "", "best_angle": ""}},
    )
    assert res.status_code == 200
    assert captured["theme"] is not None
    assert captured["theme"].target_audience == "Học sinh cấp 2"


def test_hooks_endpoint_rejects_empty_story():
    res = client.post("/api/story/hooks", json={"story": ""})
    assert res.status_code == 422


def test_generate_script_accepts_theme_and_chosen_hook(monkeypatch):
    captured = {}

    def fake_generate_script(**kwargs):
        captured.update(kwargs)
        return ScriptResult(text="kịch bản", target_word_count=100, actual_word_count=2, over_budget=False)

    monkeypatch.setattr(story_api.script_writer, "generate_script", fake_generate_script)
    res = client.post(
        "/api/story/script",
        json={
            "story": "Câu chuyện mẫu.",
            "is_long_format": True,
            "duration_minutes": 5,
            "theme": {"target_audience": "Người trẻ", "core_message": "", "audience_pain_point": "", "best_angle": ""},
            "chosen_hook": "Điều gì đã xảy ra?",
        },
    )
    assert res.status_code == 200
    assert captured["chosen_hook"] == "Điều gì đã xảy ra?"
    assert captured["theme"].target_audience == "Người trẻ"


def test_generate_script_without_theme_or_hook_still_works(monkeypatch):
    captured = {}

    def fake_generate_script(**kwargs):
        captured.update(kwargs)
        return ScriptResult(text="kịch bản", target_word_count=100, actual_word_count=2, over_budget=False)

    monkeypatch.setattr(story_api.script_writer, "generate_script", fake_generate_script)
    res = client.post(
        "/api/story/script",
        json={"story": "Câu chuyện mẫu.", "is_long_format": True, "duration_minutes": 5},
    )
    assert res.status_code == 200
    assert captured["theme"] is None
    assert captured["chosen_hook"] is None


def test_generate_script_response_includes_narration_length_fields(monkeypatch):
    monkeypatch.setattr(
        story_api.script_writer, "generate_script",
        lambda **kwargs: ScriptResult(text="kịch bản", target_word_count=100, actual_word_count=130, over_budget=True),
    )
    res = client.post(
        "/api/story/script",
        json={"story": "Câu chuyện mẫu.", "is_long_format": True, "duration_minutes": 5},
    )
    assert res.status_code == 200
    assert res.json() == {
        "script": "kịch bản",
        "narration_word_count": 130,
        "narration_target_word_count": 100,
        "narration_over_budget": True,
    }
