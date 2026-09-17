"""Bước 6-7 (Mục 3, V3): chia kịch bản thành các cảnh (storyboard) theo công
thức pacing ~8 giây/cảnh (đúc kết từ thời lượng đo thật trên 4 video cũ), rồi
sinh prompt AI tiếng Anh cho từng cảnh — LUÔN chèn lại mô tả nhân vật qua
character_bible.inject_character_descriptions() để giữ đồng nhất (Mục 5).

Phần chia thời lượng (build_scene_windows) là thuần logic, KHÔNG cần AI —
kiểm tra được bằng unit test. Phần sinh nội dung/hình ảnh cho từng cảnh
(generate_scene_prompts) cần gọi Claude.
"""
from __future__ import annotations

import re
from concurrent.futures import FIRST_EXCEPTION, ThreadPoolExecutor, wait
from dataclasses import dataclass

from app.services import llm
from app.services.character_bible import CharacterBible, inject_character_descriptions

DEFAULT_SCENE_SECONDS = 8  # công thức pacing đã đúc kết từ 4 pipeline thật (Mục 3/4, V3)

# Lỗi thật gặp phải 2026-09-15: sinh prompt TUẦN TỰ từng cảnh một khiến 1
# video dài (~37 cảnh) có thể mất HƠN 20 PHÚT chỉ để "Tạo danh sách cảnh &
# prompt", vì mỗi lượt gọi Claude qua backend CLI tốn 20-60s (spawn 1 tiến
# trình con riêng cho mỗi cảnh). Chạy song song nhiều cảnh cùng lúc (xem
# generate_scene_prompts) — giới hạn số luồng đồng thời để không làm quá
# tải CPU/RAM khi backend là CLI (mỗi luồng tự spawn 1 tiến trình con
# `claude -p`/`codex exec`/`gemini` riêng); backend API (HTTP thuần, nhẹ
# hơn nhiều) vẫn an toàn ở mức này.
#
# Đã thử 4 luồng cùng lúc trên máy dev thật (2026-09-15) và bị timeout lặp
# lại (503) giữa chừng — máy chỉ có 4 lõi CPU thật (Intel i5-9300H) và
# thường chỉ còn ~2GB RAM trống trong lúc dùng (trình duyệt + VS Code +
# chính Claude Code đang chạy cùng lúc). Mỗi luồng CLI tự mở 1 tiến trình
# Node.js riêng khá nặng — 4 tiến trình cùng lúc làm CPU/RAM quá tải,
# khiến các lượt gọi chậm hẳn hoặc vượt CLAUDE_CLI_TIMEOUT_SECONDS (180s).
# Giảm còn 2 vẫn nhanh hơn hẳn chạy tuần tự, nhưng vừa sức phần cứng hơn.
MAX_CONCURRENT_SCENE_PROMPT_CALLS = 2

# Bước 8 (Mục 3, V3): "App tự quyết cảnh nào cần video AI, cảnh nào dùng ảnh
# tĩnh, cảnh nào dùng b-roll, cảnh nào cần chữ động, cảnh nào cần biểu đồ."
# Xem app/services/scene_renderers.py cho phần dựng thật từng loại.
SCENE_TYPES = ("ai_video", "static_image", "b_roll", "motion_text", "chart")
DEFAULT_SCENE_TYPE = "ai_video"

_TIMESTAMP_RE = re.compile(r"\[(\d{2}):(\d{2})\s*-\s*(\d{2}):(\d{2})\]")

# Tên các đoạn cấu trúc kịch bản (script_writer.py) — phòng trường hợp Claude
# lỡ viết tên đoạn ngay sau dòng timestamp dù đã dặn không làm vậy (VD
# "[00:00-00:20] Hook\n..."), phải loại bỏ dòng này trước khi đưa vào TTS,
# nếu không máy đọc giọng nói sẽ đọc to luôn cả chữ "Hook" ra tiếng.
_STRUCTURE_LABELS = {
    "hook", "vấn đề", "bối cảnh", "giải pháp", "hướng dẫn",
    "ví dụ", "kết quả", "cta", "nội dung chính",
}


@dataclass
class ScriptBeat:
    start_sec: int
    end_sec: int
    text: str


@dataclass
class SceneWindow:
    scene_n: int
    start_sec: int
    end_sec: int
    source_text: str

    @property
    def duration_sec(self) -> int:
        return self.end_sec - self.start_sec


@dataclass
class ScenePrompt:
    scene_n: int
    start_sec: int
    end_sec: int
    prompt: str
    # Bước 8: loại hình dựng cho cảnh này — 1 trong SCENE_TYPES. `chart_data`
    # chỉ có giá trị khi scene_type == "chart" (xem generate_scene_prompts).
    scene_type: str = DEFAULT_SCENE_TYPE
    chart_data: dict | None = None
    # Bản dịch tiếng Việt CỦA `prompt` — CHỈ để người dùng đọc hiểu nội dung
    # cảnh trên giao diện (yêu cầu 2026-09-15), KHÔNG BAO GIỜ gửi sang Google
    # Flow (Flow luôn nhận đúng `prompt` gốc tiếng Anh). Sinh CÙNG 1 lượt gọi
    # Claude với prompt gốc, không tốn thêm request nào.
    prompt_vi: str = ""


def parse_script_beats(script_text: str) -> list[ScriptBeat]:
    """Tách kịch bản có timestamp dạng [MM:SS-MM:SS] thành từng đoạn (beat).
    Nếu kịch bản không có timestamp, trả về danh sách rỗng — caller nên yêu
    cầu viết lại kịch bản có timestamp trước khi lên storyboard."""
    matches = list(_TIMESTAMP_RE.finditer(script_text))
    beats: list[ScriptBeat] = []
    for i, m in enumerate(matches):
        start = int(m.group(1)) * 60 + int(m.group(2))
        end = int(m.group(3)) * 60 + int(m.group(4))
        text_start = m.end()
        text_end = matches[i + 1].start() if i + 1 < len(matches) else len(script_text)
        text = script_text[text_start:text_end].strip()
        first_line, sep, rest = text.partition("\n")
        if first_line.strip().lower().rstrip(":") in _STRUCTURE_LABELS:
            text = rest.strip()
        if end > start:
            beats.append(ScriptBeat(start_sec=start, end_sec=end, text=text))
    return beats


def build_scene_windows(beats: list[ScriptBeat], scene_seconds: int = DEFAULT_SCENE_SECONDS) -> list[SceneWindow]:
    """Chia mỗi beat thành các cửa sổ cảnh ~scene_seconds giây (chia đều số
    cảnh nguyên trong khoảng thời gian của beat, tối thiểu 1 cảnh/beat)."""
    windows: list[SceneWindow] = []
    scene_n = 1
    for beat in beats:
        duration = beat.end_sec - beat.start_sec
        n_scenes = max(1, round(duration / scene_seconds))
        step = duration / n_scenes
        for i in range(n_scenes):
            w_start = beat.start_sec + round(i * step)
            w_end = beat.start_sec + round((i + 1) * step) if i < n_scenes - 1 else beat.end_sec
            windows.append(SceneWindow(scene_n=scene_n, start_sec=w_start, end_sec=w_end, source_text=beat.text))
            scene_n += 1
    return windows


_SCENE_TYPE_KEYS = ", ".join(f'"{t}"' for t in SCENE_TYPES)

# Cảnh nào chèn lại mô tả nhân vật (Mục 5, V3) — chỉ 2 loại thực sự cần AI vẽ
# ra hình ảnh có thể chứa nhân vật chính; b_roll cố tình KHÔNG chèn (cảnh nền/
# toàn cảnh, không có nhân vật chính), motion_text/chart không gọi AI vẽ hình
# nên không liên quan.
_SCENE_TYPES_NEED_CHARACTER_INJECTION = {"ai_video", "static_image"}


def generate_scene_prompts(
    scene_windows: list[SceneWindow],
    bible: CharacterBible,
    style_hint: str = "cinematic, photorealistic",
    effort: str = "medium",
) -> list[ScenePrompt]:
    """Với mỗi cửa sổ cảnh, gọi Claude vừa QUYẾT ĐỊNH loại hình cảnh (Bước 8:
    video AI/ảnh tĩnh/b-roll/chữ động/biểu đồ) vừa viết prompt tương ứng —
    gộp chung 1 lượt gọi, không tốn thêm lượt Claude nào so với trước. Sau đó
    tự động chèn lại mô tả nhân vật cho 2 loại thực sự cần (ai_video,
    static_image), nếu nhân vật được nhắc trong đoạn kịch bản nguồn.

    LƯU Ý (v1): chữ trên màn hình của motion_text/chart hiện luôn ở tiếng
    Anh (giống quy ước prompt AI Bước 7) để dùng chung được cho mọi ngôn ngữ
    xuất video — xem docstring module scene_renderers.py."""
    system = (
        "You are the visual director for an AI video pipeline (style: "
        f"{style_hint}). Given a short segment of a narration script, decide "
        "which of these 5 shot types fits best, then produce the matching "
        f"content. `scene_type` MUST be exactly one of: {_SCENE_TYPE_KEYS}.\n"
        "- ai_video: the segment needs a moving shot with action/characters. "
        "`prompt` = 1-2 sentence English AI video-generation prompt, visual only.\n"
        "- static_image: the segment illustrates a static concept/moment, no "
        "motion needed. `prompt` = same style as ai_video (still an English "
        "AI image/video prompt — the still frame will be extracted from it).\n"
        "- b_roll: a wide/establishing shot with no named main character, used "
        "as filler/transition. `prompt` = English AI video-generation prompt "
        "for a generic establishing shot (no character description needed).\n"
        "- motion_text: the segment is best served by 1 short punchy phrase or "
        "keyword shown big on screen (no AI-generated visual). `prompt` = that "
        "short English phrase/keyword itself (NOT a visual description).\n"
        "- chart: the segment cites a number/comparison/statistic. `prompt` = "
        "a short English caption for the chart; ALSO fill `chart_data` as "
        '{"chart_type": "bar"|"line"|"pie", "labels": [...], "values": [...]}.\n'
        "Only use chart/motion_text when the segment is genuinely about a "
        "concept/number, not for narrative action — default to ai_video when "
        "unsure. Do not include timestamps or dialogue.\n\n"
        "ALSO fill `prompt_vi`: a Vietnamese translation of `prompt`, for a "
        "Vietnamese user to read and understand what the scene depicts — this "
        "translation is for DISPLAY ONLY, never sent to the video generator.\n\n"
        "QUAN TRỌNG VỀ ĐỊNH DẠNG: chỉ trả về đúng 1 khối JSON bọc giữa 2 dòng "
        "đánh dấu:\n===SCENE_BAT_DAU===\n"
        '{"scene_type": "...", "prompt": "...", "prompt_vi": "...", "chart_data": null}'
        "\n===SCENE_KET_THUC==="
    )
    def _generate_one(window: SceneWindow) -> ScenePrompt:
        user_prompt = f"Script segment (for context only):\n{window.source_text}"
        try:
            data = llm.generate_json(
                system, user_prompt, "===SCENE_BAT_DAU===", "===SCENE_KET_THUC===",
                max_tokens=600, effort=effort, raise_on_error=True,
            )
        except Exception as exc:
            # KHÔNG được nuốt lỗi im lặng ở đây (lỗi thật đã gặp 2026-09-15:
            # phiên Claude CLI bị gián đoạn giữa chừng khiến cả 37 cảnh lặng
            # lẽ trả về prompt RỖNG không 1 lời cảnh báo). Ném lại kèm số cảnh
            # cụ thể để người dùng biết chính xác cảnh nào và vì sao, thay vì
            # 1 lỗi chung chung — đồng thời giữ nguyên KIỂU exception gốc
            # (LlmNotConfiguredError/LlmRefusalError/LlmCliError) để lớp API
            # phía trên (app/api/storyboard.py) phân loại đúng mã lỗi.
            raise type(exc)(
                f"Không sinh được prompt cho cảnh {window.scene_n} "
                f"({window.start_sec}-{window.end_sec}s): {exc}"
            ) from exc

        scene_type = str(data.get("scene_type", DEFAULT_SCENE_TYPE)).strip()
        if scene_type not in SCENE_TYPES:
            scene_type = DEFAULT_SCENE_TYPE
        raw_prompt = str(data.get("prompt", "")).strip()
        if not raw_prompt:
            raise RuntimeError(
                f"Claude trả về prompt RỖNG cho cảnh {window.scene_n} "
                f"({window.start_sec}-{window.end_sec}s) — thử tạo lại danh sách cảnh."
            )
        prompt_vi = str(data.get("prompt_vi", "")).strip()
        chart_data = data.get("chart_data") if scene_type == "chart" and isinstance(data.get("chart_data"), dict) else None

        if scene_type in _SCENE_TYPES_NEED_CHARACTER_INJECTION:
            final_prompt = inject_character_descriptions(raw_prompt, window.source_text, bible)
        else:
            final_prompt = raw_prompt

        return ScenePrompt(
            scene_n=window.scene_n, start_sec=window.start_sec, end_sec=window.end_sec,
            prompt=final_prompt, scene_type=scene_type, chart_data=chart_data, prompt_vi=prompt_vi,
        )

    # Chạy SONG SONG nhiều cảnh cùng lúc thay vì tuần tự (xem
    # MAX_CONCURRENT_SCENE_PROMPT_CALLS) — với ~37 cảnh và backend CLI (mỗi
    # lượt gọi 20-60s), chạy tuần tự có thể mất hơn 20 phút. `executor` KHÔNG
    # dùng khối `with` (dùng try/finally thay thế) vì `with` sẽ CHỜ mọi luồng
    # đang chạy dở xong xuôi mới thoát (kể cả khi đã biết chắc thất bại) —
    # `shutdown(wait=False)` cho phép báo lỗi NGAY khi phát hiện 1 cảnh lỗi,
    # không phải đợi các cảnh khác đang gọi dở (có thể đang timeout 180s)
    # chạy xong mới thấy lỗi.
    results: list[ScenePrompt | None] = [None] * len(scene_windows)
    executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_SCENE_PROMPT_CALLS)
    try:
        future_to_index = {executor.submit(_generate_one, w): i for i, w in enumerate(scene_windows)}
        done, not_done = wait(future_to_index, return_when=FIRST_EXCEPTION)
        first_error: Exception | None = None
        for future in done:
            exc = future.exception()
            if exc is not None:
                first_error = exc
                break
        if first_error is not None:
            for f in not_done:
                f.cancel()  # chỉ huỷ được future CHƯA bắt đầu chạy, best-effort
            raise first_error
        for future in done:
            results[future_to_index[future]] = future.result()
        return results  # type: ignore[return-value]
    finally:
        executor.shutdown(wait=False)
