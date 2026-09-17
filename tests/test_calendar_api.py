"""Test app/api/calendar.py (API cho Agent "lập thực đơn tháng")."""
from fastapi.testclient import TestClient

from app.api import calendar as calendar_api
from app.main import app
from app.services.content_calendar import ScheduleSlot
from app.services.llm import LlmJsonParseError, LlmNotConfiguredError
from app.services.video_source_import import ViralFormula

client = TestClient(app)


def test_generate_calendar_success(monkeypatch):
    monkeypatch.setattr(
        calendar_api.content_calendar, "generate_topics",
        lambda strategy, slots, reference_formula=None, effort="high": [
            ScheduleSlot(day=s.day, platform=s.platform, publish_time=s.publish_time,
                         duration_seconds=s.duration_seconds, topic=f"Chủ đề {i}")
            for i, s in enumerate(slots)
        ],
    )
    res = client.post(
        "/api/calendar/generate",
        json={
            "strategy": "3 video/ngày x 3 quầy x 30 ngày",
            "platforms": ["tiktok", "facebook_instagram", "youtube"],
            "videos_per_day": 3, "days": 30, "duration_seconds": 24,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["total_videos"] == 90
    assert len(body["slots"]) == 90
    assert body["slots"][0]["topic"] == "Chủ đề 0"


def test_generate_calendar_empty_platforms_rejected_by_schema():
    """platforms=[] bị chặn ở tầng pydantic (Field min_length=1) trước khi
    vào tới content_calendar.build_schedule_grid() — 422, không phải 400."""
    res = client.post(
        "/api/calendar/generate",
        json={"strategy": "abc", "platforms": [], "videos_per_day": 1, "days": 1, "duration_seconds": 8},
    )
    assert res.status_code == 422


def test_generate_calendar_over_limit_returns_400():
    """Vượt MAX_CALENDAR_VIDEOS thì lọt qua được tầng pydantic (platforms
    không rỗng) nhưng bị build_schedule_grid() chặn -> 400 thật."""
    res = client.post(
        "/api/calendar/generate",
        json={"strategy": "abc", "platforms": ["tiktok"], "videos_per_day": 100, "days": 100, "duration_seconds": 8},
    )
    assert res.status_code == 400


def test_generate_calendar_llm_not_configured_returns_400(monkeypatch):
    def raise_not_configured(strategy, slots, reference_formula=None, effort="high"):
        raise LlmNotConfiguredError("Chưa cấu hình LLM")

    monkeypatch.setattr(calendar_api.content_calendar, "generate_topics", raise_not_configured)
    res = client.post(
        "/api/calendar/generate",
        json={"strategy": "abc", "platforms": ["tiktok"], "videos_per_day": 1, "days": 1, "duration_seconds": 8},
    )
    assert res.status_code == 400
    assert "Chưa cấu hình" in res.json()["detail"]


def test_generate_calendar_count_mismatch_returns_502(monkeypatch):
    def raise_mismatch(strategy, slots, reference_formula=None, effort="high"):
        raise LlmJsonParseError("LLM trả về 1 chủ đề, cần đúng 3")

    monkeypatch.setattr(calendar_api.content_calendar, "generate_topics", raise_mismatch)
    res = client.post(
        "/api/calendar/generate",
        json={"strategy": "abc", "platforms": ["tiktok"], "videos_per_day": 3, "days": 1, "duration_seconds": 8},
    )
    assert res.status_code == 502


def test_generate_calendar_with_reference_video_url(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        calendar_api.video_source_import, "extract_text_from_video_url", lambda url: "transcript"
    )
    monkeypatch.setattr(
        calendar_api.video_source_import, "analyze_viral_formula",
        lambda transcript: ViralFormula(hook_pattern="tò mò"),
    )

    def fake_generate_topics(strategy, slots, reference_formula=None, effort="high"):
        captured["reference_formula"] = reference_formula
        return slots

    monkeypatch.setattr(calendar_api.content_calendar, "generate_topics", fake_generate_topics)

    res = client.post(
        "/api/calendar/generate",
        json={
            "strategy": "shu theo kênh X", "platforms": ["tiktok"], "videos_per_day": 1,
            "days": 1, "duration_seconds": 8, "reference_video_url": "https://tiktok.com/@x/video/1",
        },
    )
    assert res.status_code == 200
    assert captured["reference_formula"].hook_pattern == "tò mò"


def test_generate_calendar_reference_video_transcribe_failure_returns_400(monkeypatch):
    def raise_value_error(url):
        raise ValueError("Không tải được video/audio từ link này")

    monkeypatch.setattr(calendar_api.video_source_import, "extract_text_from_video_url", raise_value_error)
    res = client.post(
        "/api/calendar/generate",
        json={
            "strategy": "abc", "platforms": ["tiktok"], "videos_per_day": 1, "days": 1,
            "duration_seconds": 8, "reference_video_url": "https://tiktok.com/@x/video/broken",
        },
    )
    assert res.status_code == 400
    assert "Không tải được" in res.json()["detail"]


def test_revise_calendar_success(monkeypatch):
    monkeypatch.setattr(
        calendar_api.content_calendar, "revise_calendar_topics",
        lambda slots, instruction, effort="medium": [
            ScheduleSlot(day=s.day, platform=s.platform, publish_time=s.publish_time,
                         duration_seconds=s.duration_seconds, topic="Chủ đề Tết")
            for s in slots
        ],
    )
    res = client.post(
        "/api/calendar/revise",
        json={
            "slots": [
                {"day": 1, "platform": "tiktok", "publish_time": "19:00", "duration_seconds": 24, "topic": "cũ"},
            ],
            "instruction": "Đổi hết sang chủ đề Tết",
        },
    )
    assert res.status_code == 200
    assert res.json()["slots"][0]["topic"] == "Chủ đề Tết"


def test_revise_calendar_empty_instruction_returns_400():
    """Không mock revise_calendar_topics — kiểm tra thật đường dẫn ValueError
    (từ content_calendar.revise_calendar_topics) -> HTTPException 400."""
    res = client.post(
        "/api/calendar/revise",
        json={
            "slots": [
                {"day": 1, "platform": "tiktok", "publish_time": "19:00", "duration_seconds": 24},
            ],
            "instruction": "",
        },
    )
    assert res.status_code == 422  # Field(min_length=1) chặn ở tầng pydantic trước khi vào hàm
