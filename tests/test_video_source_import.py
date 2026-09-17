"""Test app/services/video_source_import.py (agent phân tích nguồn video).
Mock video_transcribe.transcribe_video_url() (không tải/nhận diện thật) và
llm.generate_json() (không gọi LLM thật) — đúng tinh thần dự án."""
import pytest

from app.services import video_source_import, video_transcribe


def test_extract_text_from_video_url_returns_transcript(monkeypatch):
    monkeypatch.setattr(
        video_transcribe, "transcribe_video_url",
        lambda url, **kwargs: video_transcribe.TranscriptResult(text="lời nói trong video", language="vi"),
    )
    text = video_source_import.extract_text_from_video_url("https://tiktok.com/@x/video/1")
    assert text == "lời nói trong video"


def test_extract_text_from_video_url_passes_model_size(monkeypatch):
    captured = {}

    def fake_transcribe(url, **kwargs):
        captured.update(kwargs)
        return video_transcribe.TranscriptResult(text="ok", language="vi")

    monkeypatch.setattr(video_transcribe, "transcribe_video_url", fake_transcribe)
    video_source_import.extract_text_from_video_url("https://x.com/1", model_size="base")
    assert captured == {"model_size": "base"}


def test_extract_text_from_video_url_propagates_not_configured(monkeypatch):
    def raise_not_configured(url, **kwargs):
        raise video_transcribe.TranscribeNotConfiguredError("Chưa cài yt-dlp")

    monkeypatch.setattr(video_transcribe, "transcribe_video_url", raise_not_configured)
    with pytest.raises(video_transcribe.TranscribeNotConfiguredError):
        video_source_import.extract_text_from_video_url("https://x.com/1")


def test_analyze_viral_formula_rejects_empty_transcript():
    with pytest.raises(ValueError, match="Không có nội dung"):
        video_source_import.analyze_viral_formula("   ")


def test_analyze_viral_formula_parses_llm_result(monkeypatch):
    captured = {}

    def fake_generate_json(system, user_prompt, start, end, max_tokens=1500, effort="medium", default=None, raise_on_error=False):
        captured["user_prompt"] = user_prompt
        return {
            "hook_pattern": "câu hỏi gây tò mò",
            "structure_beats": ["Hook", "Twist", "CTA"],
            "pacing_style": "nhanh, nhiều twist",
            "cta_type": "kêu gọi theo dõi",
            "tone": "hài hước",
            "why_it_works": "Giữ chân người xem bằng twist bất ngờ.",
        }

    monkeypatch.setattr(video_source_import.llm, "generate_json", fake_generate_json)
    formula = video_source_import.analyze_viral_formula("Đây là transcript video hot.")

    assert formula.hook_pattern == "câu hỏi gây tò mò"
    assert formula.structure_beats == ["Hook", "Twist", "CTA"]
    assert formula.pacing_style == "nhanh, nhiều twist"
    assert formula.cta_type == "kêu gọi theo dõi"
    assert formula.tone == "hài hước"
    assert formula.why_it_works == "Giữ chân người xem bằng twist bất ngờ."
    assert "Đây là transcript video hot." in captured["user_prompt"]


def test_analyze_viral_formula_handles_missing_beats_gracefully(monkeypatch):
    monkeypatch.setattr(
        video_source_import.llm, "generate_json",
        lambda *a, **k: {"hook_pattern": "x"},
    )
    formula = video_source_import.analyze_viral_formula("transcript")
    assert formula.hook_pattern == "x"
    assert formula.structure_beats == []


def test_analyze_viral_formula_truncates_long_transcript(monkeypatch):
    captured = {}

    def fake_generate_json(system, user_prompt, *a, **k):
        captured["len"] = len(user_prompt)
        return {}

    monkeypatch.setattr(video_source_import.llm, "generate_json", fake_generate_json)
    video_source_import.analyze_viral_formula("x" * (video_source_import.MAX_TRANSCRIPT_CHARS + 5000))
    assert captured["len"] < video_source_import.MAX_TRANSCRIPT_CHARS + 5000
