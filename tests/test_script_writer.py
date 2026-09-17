"""Test script_writer mà KHÔNG cần API key thật — mock llm.generate_text và
kiểm tra prompt lắp ráp đúng cấu trúc/thời lượng/ngôn ngữ theo V3, vì phần
gọi Claude thật không thể live-test khi chưa có key (xem README)."""
import app.services.script_writer as script_writer


def test_rewrite_story_calls_llm_with_idea(monkeypatch):
    captured = {}

    def fake_generate_text(system, user_prompt, max_tokens=16000, effort="high"):
        captured["system"] = system
        captured["user_prompt"] = user_prompt
        return "Câu chuyện đã viết lại."

    monkeypatch.setattr(script_writer.llm, "generate_text", fake_generate_text)

    result = script_writer.rewrite_story("Một chú chó lạc đường tìm về nhà.")

    assert result == "Câu chuyện đã viết lại."
    assert "Một chú chó lạc đường" in captured["user_prompt"]


def test_generate_script_long_format_includes_full_structure(monkeypatch):
    captured = {}

    def fake_generate_text(system, user_prompt, max_tokens=16000, effort="high"):
        captured["system"] = system
        captured["user_prompt"] = user_prompt
        captured["max_tokens"] = max_tokens
        return "kịch bản"

    monkeypatch.setattr(script_writer.llm, "generate_text", fake_generate_text)

    script_writer.generate_script(
        story="Câu chuyện nền.",
        is_long_format=True,
        duration_minutes=10,
        duration_seconds=None,
        language_name="Tiếng Anh",
    )

    for part in script_writer.LONG_STRUCTURE:
        assert part in captured["system"]
    assert "10 phút" in captured["user_prompt"]
    assert "Tiếng Anh" in captured["system"]


def test_generate_script_short_format_uses_short_structure(monkeypatch):
    captured = {}

    def fake_generate_text(system, user_prompt, max_tokens=16000, effort="high"):
        captured["system"] = system
        captured["user_prompt"] = user_prompt
        return "kịch bản ngắn"

    monkeypatch.setattr(script_writer.llm, "generate_text", fake_generate_text)

    script_writer.generate_script(
        story="Câu chuyện nền.",
        is_long_format=False,
        duration_minutes=None,
        duration_seconds=30,
        language_name="Tiếng Việt",
    )

    for part in script_writer.SHORT_STRUCTURE:
        assert part in captured["system"]
    assert "Bối cảnh" not in captured["system"]  # phần dài không lẫn vào bản short
    assert "30 giây" in captured["user_prompt"]


def test_estimate_max_tokens_scales_with_duration_and_has_floor():
    short = script_writer._estimate_max_tokens(None, 15)
    long = script_writer._estimate_max_tokens(30, None)
    assert short >= 6000
    assert long > short


def test_determine_theme_and_goals_parses_fields(monkeypatch):
    fake_response = {
        "target_audience": "Người trẻ 18-30 tuổi thích lịch sử",
        "audience_pain_point": "Thấy sử Việt khô khan, khó nhớ",
        "core_message": "Lịch sử có thể kể hấp dẫn như phim sử thi",
        "best_angle": "Kể theo góc nhìn nhân vật chính giữa trận đánh",
    }
    monkeypatch.setattr(script_writer.llm, "generate_json", lambda *a, **k: fake_response)

    result = script_writer.determine_theme_and_goals("Câu chuyện Quang Trung.")
    assert result.target_audience == "Người trẻ 18-30 tuổi thích lịch sử"
    assert result.core_message == "Lịch sử có thể kể hấp dẫn như phim sử thi"


def test_determine_theme_and_goals_empty_on_failure(monkeypatch):
    monkeypatch.setattr(script_writer.llm, "generate_json", lambda *a, **k: {})
    result = script_writer.determine_theme_and_goals("Câu chuyện bất kỳ.")
    assert result.target_audience == ""
    assert result.best_angle == ""


def test_generate_hooks_parses_candidates_and_top3(monkeypatch):
    fake_response = {
        "candidates": [
            {"group": "to_mo", "text": "Điều gì đã xảy ra trong 5 ngày đó?"},
            {"group": "bat_ngo", "text": "Không ai ngờ trận đánh kết thúc như vậy."},
        ],
        "top_3": ["Điều gì đã xảy ra trong 5 ngày đó?", "Câu 2", "Câu 3"],
    }
    monkeypatch.setattr(script_writer.llm, "generate_json", lambda *a, **k: fake_response)

    result = script_writer.generate_hooks("Câu chuyện Quang Trung.")
    assert len(result.candidates) == 2
    assert result.candidates[0].group == "to_mo"
    assert len(result.top_3) == 3


def test_generate_hooks_includes_theme_context_when_given(monkeypatch):
    captured = {}

    def fake_generate_json(system, user_prompt, *a, **k):
        captured["user_prompt"] = user_prompt
        return {"candidates": [], "top_3": []}

    monkeypatch.setattr(script_writer.llm, "generate_json", fake_generate_json)
    theme = script_writer.ThemeAndGoals(
        target_audience="Học sinh cấp 2", core_message="Lòng dũng cảm", best_angle="Kể theo nhật ký"
    )
    script_writer.generate_hooks("Câu chuyện.", theme=theme)
    assert "Học sinh cấp 2" in captured["user_prompt"]
    assert "Lòng dũng cảm" in captured["user_prompt"]


def test_generate_hooks_empty_on_failure(monkeypatch):
    monkeypatch.setattr(script_writer.llm, "generate_json", lambda *a, **k: {})
    result = script_writer.generate_hooks("Câu chuyện.")
    assert result.candidates == []
    assert result.top_3 == []


def test_generate_script_includes_chosen_hook_instruction(monkeypatch):
    captured = {}

    def fake_generate_text(system, user_prompt, max_tokens=16000, effort="high"):
        captured["system"] = system
        return "kịch bản"

    monkeypatch.setattr(script_writer.llm, "generate_text", fake_generate_text)
    script_writer.generate_script(
        story="Câu chuyện nền.", is_long_format=True, duration_minutes=5, duration_seconds=None,
        chosen_hook="Điều gì đã xảy ra trong 5 ngày đó?",
    )
    assert "Điều gì đã xảy ra trong 5 ngày đó?" in captured["system"]


def test_generate_script_includes_theme_instruction(monkeypatch):
    captured = {}

    def fake_generate_text(system, user_prompt, max_tokens=16000, effort="high"):
        captured["system"] = system
        return "kịch bản"

    monkeypatch.setattr(script_writer.llm, "generate_text", fake_generate_text)
    theme = script_writer.ThemeAndGoals(
        target_audience="Người trẻ yêu lịch sử", core_message="Đoàn kết làm nên sức mạnh", best_angle="Góc nhìn binh sĩ"
    )
    script_writer.generate_script(
        story="Câu chuyện nền.", is_long_format=True, duration_minutes=5, duration_seconds=None, theme=theme,
    )
    assert "Người trẻ yêu lịch sử" in captured["system"]
    assert "Đoàn kết làm nên sức mạnh" in captured["system"]


def test_generate_script_without_theme_or_hook_unchanged(monkeypatch):
    """Không truyền theme/chosen_hook -> hành vi y hệt trước khi thêm Bước 3/4."""
    captured = {}

    def fake_generate_text(system, user_prompt, max_tokens=16000, effort="high"):
        captured["system"] = system
        return "kịch bản"

    monkeypatch.setattr(script_writer.llm, "generate_text", fake_generate_text)
    script_writer.generate_script(
        story="Câu chuyện nền.", is_long_format=False, duration_minutes=None, duration_seconds=30,
    )
    assert captured["system"].rstrip().endswith("đầu dòng lời thoại.")


# --- Skill 11 (narration-length-budget, 2026-09-15) ---------------------


def test_target_narration_word_count_uses_150wpm_with_margin():
    # 60s ở 150 từ/phút = 150 từ; dư 12.5% -> ~131 từ.
    assert script_writer.target_narration_word_count(None, 60) == round(150 * 0.875)
    # 5 phút = 300s -> 750 từ lý thuyết; dư 12.5% -> ~656 từ.
    assert script_writer.target_narration_word_count(5, None) == round(750 * 0.875)


def test_count_narration_words_ignores_timestamps():
    text = "[00:00-00:20] Một câu lời đọc năm từ đây.\n[00:20-00:35] Ba từ nữa thôi."
    # "Một câu lời đọc năm từ đây." = 7 từ; "Ba từ nữa thôi." = 4 từ.
    assert script_writer.count_narration_words(text) == 11


def test_generate_script_system_prompt_bans_visual_descriptions_and_sets_word_budget(monkeypatch):
    captured = {}

    def fake_generate_text(system, user_prompt, max_tokens=16000, effort="high"):
        captured["system"] = system
        captured["user_prompt"] = user_prompt
        return "kịch bản"

    monkeypatch.setattr(script_writer.llm, "generate_text", fake_generate_text)
    script_writer.generate_script(
        story="Câu chuyện nền.", is_long_format=True, duration_minutes=5, duration_seconds=None,
    )
    assert "(Hình ảnh:" in captured["system"]  # cấm rõ đúng mẫu đã gây lỗi thật
    target = script_writer.target_narration_word_count(5, None)
    assert str(target) in captured["system"]
    assert str(target) in captured["user_prompt"]


def test_generate_script_returns_result_with_word_counts(monkeypatch):
    monkeypatch.setattr(script_writer.llm, "generate_text", lambda *a, **k: "[00:00-00:10] Một hai ba bốn năm.")
    result = script_writer.generate_script(
        story="Câu chuyện nền.", is_long_format=False, duration_minutes=None, duration_seconds=10,
    )
    assert isinstance(result, script_writer.ScriptResult)
    assert result.text == "[00:00-00:10] Một hai ba bốn năm."
    assert result.actual_word_count == 5
    assert result.target_word_count == script_writer.target_narration_word_count(None, 10)
    assert result.over_budget is False


def test_generate_script_flags_over_budget_when_too_long(monkeypatch):
    long_text = "[00:00-00:10] " + " ".join(["từ"] * 200)  # cực dài so với ngân sách 10s
    monkeypatch.setattr(script_writer.llm, "generate_text", lambda *a, **k: long_text)
    result = script_writer.generate_script(
        story="Câu chuyện nền.", is_long_format=False, duration_minutes=None, duration_seconds=10,
    )
    assert result.over_budget is True
