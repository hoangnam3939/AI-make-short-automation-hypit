"""Test app/services/content_calendar.py (Agent "lập thực đơn tháng").
build_schedule_grid() là toán thuần (không mock) — kiểm tra thật đúng số
lượng/round-robin. generate_topics()/revise_calendar_topics() mock
llm.generate_json (không gọi LLM thật), đúng tinh thần dự án."""
import pytest

from app.services import content_calendar
from app.services.content_calendar import ScheduleSlot
from app.services.llm import LlmJsonParseError
from app.services.video_source_import import ViralFormula


def test_build_schedule_grid_matches_kh_app_example():
    """Đúng ví dụ trong KH App new: 3 video/ngày x 3 quầy x 30 ngày = 90 video."""
    slots = content_calendar.build_schedule_grid(
        platforms=["tiktok", "facebook_instagram", "youtube"],
        videos_per_day=3, days=30, duration_seconds=24,
    )
    assert len(slots) == 90
    assert all(s.duration_seconds == 24 for s in slots)
    # Mỗi quầy nhận đúng 30 video (1 video/ngày/quầy).
    for platform in ("tiktok", "facebook_instagram", "youtube"):
        assert sum(1 for s in slots if s.platform == platform) == 30
    # Ngày 1: đúng 1 video mỗi quầy, đúng thứ tự round-robin.
    day1 = [s for s in slots if s.day == 1]
    assert [s.platform for s in day1] == ["tiktok", "facebook_instagram", "youtube"]


def test_build_schedule_grid_uses_default_golden_hours():
    slots = content_calendar.build_schedule_grid(["tiktok"], videos_per_day=1, days=1, duration_seconds=8)
    assert slots[0].publish_time == content_calendar.DEFAULT_GOLDEN_HOURS["tiktok"]


def test_build_schedule_grid_golden_hours_override():
    slots = content_calendar.build_schedule_grid(
        ["tiktok"], videos_per_day=1, days=1, duration_seconds=8, golden_hours={"tiktok": "22:15"},
    )
    assert slots[0].publish_time == "22:15"


def test_build_schedule_grid_rejects_empty_platforms():
    with pytest.raises(ValueError, match="quầy hàng"):
        content_calendar.build_schedule_grid([], videos_per_day=1, days=1, duration_seconds=8)


def test_build_schedule_grid_rejects_zero_videos_per_day():
    with pytest.raises(ValueError, match="videos_per_day"):
        content_calendar.build_schedule_grid(["tiktok"], videos_per_day=0, days=1, duration_seconds=8)


def test_build_schedule_grid_rejects_zero_days():
    with pytest.raises(ValueError, match="days"):
        content_calendar.build_schedule_grid(["tiktok"], videos_per_day=1, days=0, duration_seconds=8)


def test_build_schedule_grid_rejects_over_limit():
    with pytest.raises(ValueError, match="vượt giới hạn"):
        content_calendar.build_schedule_grid(
            ["tiktok"], videos_per_day=100, days=100, duration_seconds=8,
        )


def _make_slots(n=3):
    return [ScheduleSlot(day=1, platform="tiktok", publish_time="19:00", duration_seconds=24) for _ in range(n)]


def test_generate_topics_fills_slots_in_order(monkeypatch):
    captured = {}

    def fake_generate_json(system, user_prompt, start, end, max_tokens=1500, effort="medium", default=None, raise_on_error=False):
        captured["system"] = system
        captured["user_prompt"] = user_prompt
        return [
            {"topic": "Chủ đề 1", "angle": "Góc 1", "hook_idea": "Hook 1"},
            {"topic": "Chủ đề 2", "angle": "Góc 2", "hook_idea": "Hook 2"},
            {"topic": "Chủ đề 3", "angle": "Góc 3", "hook_idea": "Hook 3"},
        ]

    monkeypatch.setattr(content_calendar.llm, "generate_json", fake_generate_json)
    slots = _make_slots(3)
    result = content_calendar.generate_topics("Chiến lược ABC", slots)

    assert [s.topic for s in result] == ["Chủ đề 1", "Chủ đề 2", "Chủ đề 3"]
    assert [s.angle for s in result] == ["Góc 1", "Góc 2", "Góc 3"]
    assert [s.hook_idea for s in result] == ["Hook 1", "Hook 2", "Hook 3"]
    assert "Chiến lược ABC" in captured["system"]


def test_generate_topics_rejects_empty_strategy():
    with pytest.raises(ValueError, match="câu chiến lược"):
        content_calendar.generate_topics("   ", _make_slots(1))


def test_generate_topics_rejects_empty_slots():
    with pytest.raises(ValueError, match="Chưa có lịch"):
        content_calendar.generate_topics("Chiến lược ABC", [])


def test_generate_topics_raises_on_count_mismatch(monkeypatch):
    monkeypatch.setattr(
        content_calendar.llm, "generate_json",
        lambda *a, **k: [{"topic": "chỉ 1", "angle": "", "hook_idea": ""}],
    )
    with pytest.raises(LlmJsonParseError, match="cần đúng 3"):
        content_calendar.generate_topics("Chiến lược ABC", _make_slots(3))


def test_generate_topics_includes_reference_formula_in_prompt(monkeypatch):
    captured = {}

    def fake_generate_json(system, user_prompt, start, end, max_tokens=1500, effort="medium", default=None, raise_on_error=False):
        captured["system"] = system
        return [{"topic": "t", "angle": "a", "hook_idea": "h"}]

    monkeypatch.setattr(content_calendar.llm, "generate_json", fake_generate_json)
    formula = ViralFormula(
        hook_pattern="câu hỏi gây tò mò", structure_beats=["Hook", "Twist", "CTA"],
        pacing_style="nhanh", cta_type="theo dõi", tone="hài hước",
    )
    content_calendar.generate_topics("Chiến lược ABC", _make_slots(1), reference_formula=formula)

    assert "câu hỏi gây tò mò" in captured["system"]
    assert "Hook, Twist, CTA" in captured["system"]


def test_revise_calendar_topics_updates_all_slots(monkeypatch):
    monkeypatch.setattr(
        content_calendar.llm, "generate_json",
        lambda *a, **k: [
            {"topic": "Chủ đề mới 1", "angle": "Góc mới 1", "hook_idea": "Hook mới 1"},
            {"topic": "Chủ đề mới 2", "angle": "Góc mới 2", "hook_idea": "Hook mới 2"},
        ],
    )
    slots = _make_slots(2)
    slots[0].topic = "Chủ đề cũ 1"
    result = content_calendar.revise_calendar_topics(slots, "Đổi hết sang chủ đề Tết")

    assert [s.topic for s in result] == ["Chủ đề mới 1", "Chủ đề mới 2"]


def test_revise_calendar_topics_rejects_empty_instruction():
    with pytest.raises(ValueError, match="yêu cầu chỉnh sửa"):
        content_calendar.revise_calendar_topics(_make_slots(1), "   ")


def test_revise_calendar_topics_rejects_empty_slots():
    with pytest.raises(ValueError, match="Chưa có thực đơn"):
        content_calendar.revise_calendar_topics([], "sửa gì đó")


def test_generate_content_calendar_end_to_end(monkeypatch):
    monkeypatch.setattr(
        content_calendar.llm, "generate_json",
        lambda system, user_prompt, start, end, max_tokens=1500, effort="medium", default=None, raise_on_error=False: [
            {"topic": f"Chủ đề {i}", "angle": "", "hook_idea": ""} for i in range(6)
        ],
    )
    calendar = content_calendar.generate_content_calendar(
        strategy="3 video/ngày x 2 quầy x 3 ngày", platforms=["tiktok", "youtube"],
        videos_per_day=2, days=3, duration_seconds=16,
    )
    assert calendar.total_videos == 6
    assert len(calendar.slots) == 6
    assert calendar.strategy_summary == "3 video/ngày x 2 quầy x 3 ngày"
    assert all(s.topic for s in calendar.slots)
