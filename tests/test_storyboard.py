import pytest

import app.services.storyboard as storyboard
from app.services.character_bible import Character, CharacterBible
from app.services.llm import LlmCliError, LlmNotConfiguredError


SAMPLE_SCRIPT = (
    "[00:00-00:16] Gióng vươn vai đứng dậy, khoác lên mình bộ áo giáp sắt.\n"
    "[00:16-00:24] Chàng phi ngựa sắt xông ra trận."
)


def test_parse_script_beats_extracts_timestamps_and_text():
    beats = storyboard.parse_script_beats(SAMPLE_SCRIPT)
    assert len(beats) == 2
    assert beats[0].start_sec == 0 and beats[0].end_sec == 16
    assert "áo giáp sắt" in beats[0].text
    assert beats[1].start_sec == 16 and beats[1].end_sec == 24


def test_parse_script_beats_returns_empty_without_timestamps():
    assert storyboard.parse_script_beats("Kịch bản không có timestamp.") == []


def test_parse_script_beats_strips_structure_label_line():
    """Lỗi thật đã phòng: Claude có thể lỡ viết tên đoạn (Hook, Vấn đề...)
    ngay dòng đầu sau timestamp dù đã dặn không làm vậy — dòng này phải bị
    loại bỏ, không được lẫn vào văn bản đưa cho TTS đọc."""
    script = (
        "[00:00-00:20] Hook\n"
        "Đêm giao thừa, năm 1789.\n"
        "[00:20-00:40] Vấn đề\n"
        "Bắt đầu từ một sự phản bội."
    )
    beats = storyboard.parse_script_beats(script)
    assert beats[0].text == "Đêm giao thừa, năm 1789."
    assert "hook" not in beats[0].text.lower()
    assert beats[1].text == "Bắt đầu từ một sự phản bội."
    assert "vấn đề" not in beats[1].text.lower()


def test_build_scene_windows_splits_by_8_seconds():
    beats = storyboard.parse_script_beats(SAMPLE_SCRIPT)
    windows = storyboard.build_scene_windows(beats, scene_seconds=8)

    # beat 1: 16s / 8s = 2 canh; beat 2: 8s / 8s = 1 canh
    assert len(windows) == 3
    assert windows[0].start_sec == 0 and windows[0].end_sec == 8
    assert windows[1].start_sec == 8 and windows[1].end_sec == 16
    assert windows[2].start_sec == 16 and windows[2].end_sec == 24
    # scene_n phải liên tục tăng dần qua toàn bộ storyboard
    assert [w.scene_n for w in windows] == [1, 2, 3]


def test_build_scene_windows_minimum_one_scene_per_beat():
    beats = [storyboard.ScriptBeat(start_sec=0, end_sec=3, text="canh rat ngan")]
    windows = storyboard.build_scene_windows(beats, scene_seconds=8)
    assert len(windows) == 1
    assert windows[0].start_sec == 0 and windows[0].end_sec == 3


def test_build_scene_windows_covers_full_beat_duration_with_no_gaps():
    beats = [storyboard.ScriptBeat(start_sec=0, end_sec=25, text="canh dai le")]
    windows = storyboard.build_scene_windows(beats, scene_seconds=8)
    assert windows[0].start_sec == 0
    assert windows[-1].end_sec == 25
    for prev, nxt in zip(windows, windows[1:]):
        assert prev.end_sec == nxt.start_sec  # khong co khoang trong giua cac canh


def test_generate_scene_prompts_injects_character_description(monkeypatch):
    bible = CharacterBible()
    bible.add(Character(
        name="Gióng",
        description="wearing heavy gleaming iron armor, NOT an oversized bare-chested bodybuilder",
    ))
    windows = [
        storyboard.SceneWindow(scene_n=1, start_sec=0, end_sec=8, source_text="Gióng khoác áo giáp sắt."),
    ]

    def fake_generate_json(system, user_prompt, *a, **k):
        return {"scene_type": "ai_video", "prompt": "Wide shot of the warrior standing up, ready for battle."}

    monkeypatch.setattr(storyboard.llm, "generate_json", fake_generate_json)

    prompts = storyboard.generate_scene_prompts(windows, bible)

    assert len(prompts) == 1
    assert prompts[0].scene_type == "ai_video"
    assert "gleaming iron armor" in prompts[0].prompt
    assert "ready for battle" in prompts[0].prompt


def test_generate_scene_prompts_skips_injection_when_character_not_in_scene(monkeypatch):
    bible = CharacterBible()
    bible.add(Character(name="Gióng", description="gleaming iron armor"))
    windows = [
        storyboard.SceneWindow(scene_n=1, start_sec=0, end_sec=8, source_text="Trời đêm yên tĩnh trên đỉnh núi."),
    ]

    monkeypatch.setattr(
        storyboard.llm, "generate_json",
        lambda *a, **k: {"scene_type": "ai_video", "prompt": "A quiet mountain peak at night."},
    )

    prompts = storyboard.generate_scene_prompts(windows, bible)
    assert "gleaming iron armor" not in prompts[0].prompt


def test_generate_scene_prompts_b_roll_skips_injection_even_when_character_mentioned(monkeypatch):
    """Bước 8: b_roll là cảnh nền/toàn cảnh, KHÔNG chèn mô tả nhân vật dù tên
    nhân vật có bị nhắc trong đoạn kịch bản nguồn (khác ai_video/static_image)."""
    bible = CharacterBible()
    bible.add(Character(name="Gióng", description="gleaming iron armor"))
    windows = [
        storyboard.SceneWindow(scene_n=1, start_sec=0, end_sec=8, source_text="Gióng nhìn ra cánh đồng rộng lớn."),
    ]
    monkeypatch.setattr(
        storyboard.llm, "generate_json",
        lambda *a, **k: {"scene_type": "b_roll", "prompt": "Wide establishing shot of a vast rice field."},
    )
    prompts = storyboard.generate_scene_prompts(windows, bible)
    assert prompts[0].scene_type == "b_roll"
    assert "gleaming iron armor" not in prompts[0].prompt


def test_generate_scene_prompts_chart_type_keeps_chart_data(monkeypatch):
    bible = CharacterBible()
    windows = [
        storyboard.SceneWindow(scene_n=1, start_sec=0, end_sec=8, source_text="Quân số 5 vạn so với 20 vạn."),
    ]
    monkeypatch.setattr(
        storyboard.llm, "generate_json",
        lambda *a, **k: {
            "scene_type": "chart", "prompt": "Army size comparison",
            "chart_data": {"chart_type": "bar", "labels": ["Ta", "Địch"], "values": [5, 20]},
        },
    )
    prompts = storyboard.generate_scene_prompts(windows, bible)
    assert prompts[0].scene_type == "chart"
    assert prompts[0].chart_data == {"chart_type": "bar", "labels": ["Ta", "Địch"], "values": [5, 20]}


def test_generate_scene_prompts_falls_back_to_ai_video_on_unknown_type(monkeypatch):
    bible = CharacterBible()
    windows = [storyboard.SceneWindow(scene_n=1, start_sec=0, end_sec=8, source_text="Cảnh bất kỳ.")]
    monkeypatch.setattr(
        storyboard.llm, "generate_json",
        lambda *a, **k: {"scene_type": "khong-hop-le", "prompt": "A generic shot."},
    )
    prompts = storyboard.generate_scene_prompts(windows, bible)
    assert prompts[0].scene_type == "ai_video"


def test_generate_scene_prompts_raises_on_empty_prompt_instead_of_silently_defaulting(monkeypatch):
    """Lỗi thật đã gặp 2026-09-15: khi phiên Claude CLI bị gián đoạn giữa
    chừng, hành vi cũ (nuốt lỗi, mặc định prompt rỗng) khiến cả 37 cảnh lặng
    lẽ trả về prompt RỖNG không 1 lời cảnh báo — người dùng tưởng app chạy
    xong (thấy đủ "Cảnh 1, Cảnh 2, ... Cảnh 37") nhưng thực ra mọi cảnh đều
    thất bại. Giờ phải RAISE rõ ràng thay vì âm thầm trả prompt rỗng."""
    bible = CharacterBible()
    windows = [storyboard.SceneWindow(scene_n=5, start_sec=32, end_sec=40, source_text="Cảnh bất kỳ.")]
    monkeypatch.setattr(storyboard.llm, "generate_json", lambda *a, **k: {})
    with pytest.raises(RuntimeError, match="cảnh 5"):
        storyboard.generate_scene_prompts(windows, bible)


def test_generate_scene_prompts_calls_llm_with_raise_on_error(monkeypatch):
    captured = {}

    def fake_generate_json(system, user_prompt, *a, **k):
        captured.update(k)
        return {"scene_type": "ai_video", "prompt": "A shot.", "prompt_vi": "Một cảnh quay."}

    bible = CharacterBible()
    windows = [storyboard.SceneWindow(scene_n=1, start_sec=0, end_sec=8, source_text="Cảnh bất kỳ.")]
    monkeypatch.setattr(storyboard.llm, "generate_json", fake_generate_json)
    storyboard.generate_scene_prompts(windows, bible)
    assert captured.get("raise_on_error") is True


@pytest.mark.parametrize("error_cls", [LlmNotConfiguredError, LlmCliError])
def test_generate_scene_prompts_propagates_llm_errors_with_scene_context(monkeypatch, error_cls):
    """Lớp API (app/api/storyboard.py) phân loại mã lỗi HTTP theo ĐÚNG kiểu
    exception gốc — phải giữ nguyên kiểu khi bọc thêm ngữ cảnh số cảnh."""
    bible = CharacterBible()
    windows = [storyboard.SceneWindow(scene_n=3, start_sec=16, end_sec=24, source_text="Cảnh bất kỳ.")]

    def fake_generate_json(*a, **k):
        raise error_cls("lỗi giả lập")

    monkeypatch.setattr(storyboard.llm, "generate_json", fake_generate_json)
    with pytest.raises(error_cls, match="cảnh 3"):
        storyboard.generate_scene_prompts(windows, bible)


def test_generate_scene_prompts_captures_vietnamese_translation(monkeypatch):
    bible = CharacterBible()
    windows = [storyboard.SceneWindow(scene_n=1, start_sec=0, end_sec=8, source_text="Cảnh bất kỳ.")]
    monkeypatch.setattr(
        storyboard.llm, "generate_json",
        lambda *a, **k: {"scene_type": "ai_video", "prompt": "A warrior charges forward.", "prompt_vi": "Một chiến binh xông lên phía trước."},
    )
    prompts = storyboard.generate_scene_prompts(windows, bible)
    assert prompts[0].prompt == "A warrior charges forward."
    assert prompts[0].prompt_vi == "Một chiến binh xông lên phía trước."


# --- Sinh prompt SONG SONG (2026-09-15): sinh tuần tự cho ~37 cảnh với ----
# backend CLI (mỗi lượt gọi 20-60s) có thể mất hơn 20 phút — xem
# MAX_CONCURRENT_SCENE_PROMPT_CALLS trong storyboard.py.
# ---------------------------------------------------------------------------

def test_generate_scene_prompts_preserves_order_despite_concurrent_completion(monkeypatch):
    """Các lượt gọi chạy song song có thể hoàn thành KHÔNG theo thứ tự (cảnh
    lẻ giả lập nhanh hơn cảnh chẵn) — kết quả trả về vẫn phải ĐÚNG thứ tự
    scene_n như đầu vào."""
    import time

    bible = CharacterBible()
    windows = [
        storyboard.SceneWindow(scene_n=i, start_sec=(i - 1) * 8, end_sec=i * 8, source_text=f"scene-{i}")
        for i in range(1, 9)
    ]

    def fake_generate_json(system, user_prompt, *a, **k):
        scene_num = int(user_prompt.rsplit("scene-", 1)[1])
        time.sleep(0.05 if scene_num % 2 == 1 else 0.01)
        return {"scene_type": "ai_video", "prompt": f"Prompt {scene_num}", "prompt_vi": ""}

    monkeypatch.setattr(storyboard.llm, "generate_json", fake_generate_json)
    prompts = storyboard.generate_scene_prompts(windows, bible)
    assert [p.scene_n for p in prompts] == list(range(1, 9))
    assert [p.prompt for p in prompts] == [f"Prompt {i}" for i in range(1, 9)]


def test_generate_scene_prompts_raises_promptly_when_one_of_many_fails(monkeypatch):
    """1 cảnh lỗi giữa nhiều cảnh khác vẫn phải báo lỗi rõ ràng — không được
    yêu cầu chờ TOÀN BỘ các cảnh khác (có thể đang timeout riêng) chạy xong
    mới báo, và không được nuốt lỗi im lặng."""
    bible = CharacterBible()
    windows = [
        storyboard.SceneWindow(scene_n=i, start_sec=(i - 1) * 8, end_sec=i * 8, source_text=f"scene-{i}")
        for i in range(1, 6)
    ]

    def fake_generate_json(system, user_prompt, *a, **k):
        scene_num = int(user_prompt.rsplit("scene-", 1)[1])
        if scene_num == 3:
            raise LlmCliError("lỗi giả lập cho cảnh 3")
        return {"scene_type": "ai_video", "prompt": f"Prompt {scene_num}", "prompt_vi": ""}

    monkeypatch.setattr(storyboard.llm, "generate_json", fake_generate_json)
    with pytest.raises(LlmCliError, match="cảnh 3"):
        storyboard.generate_scene_prompts(windows, bible)
