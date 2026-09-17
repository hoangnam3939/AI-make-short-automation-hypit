"""Dựng lại SFX (Bước 13) cho video Quang Trung (Việt + Anh) theo ĐÚNG TỪNG
CẢNH storyboard thay vì theo cả đoạn lời dẫn — sửa lỗi thật đã sửa trong
app/services/sfx_sourcing.py (xem .claude/skills/sfx-mixing-safety/SKILL.md).

Điểm quan trọng: vì Bước 10 ghép video theo đúng độ dài GIỌNG ĐỌC của cả
đoạn, nhiều cảnh storyboard bị CẮT MẤT một phần hoặc TOÀN BỘ trong video
cuối (giọng đọc ngắn hơn tổng thời lượng Flow đã tạo cho đoạn đó). Script
này tự tính đúng phần THẬT SỰ HIỂN THỊ của mỗi cảnh (đo bằng ffprobe trên
chính file đã dựng), chỉ xin gợi ý SFX cho phần thật sự lên hình, và giới
hạn đúng offset tuyệt đối trong toàn bộ video.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from app.services.llm import suggest_sfx_layers  # noqa: E402
from app.services.sfx_sourcing import (  # noqa: E402
    ScenePlan,
    SfxLayer,
    apply_step13_sfx,
    build_sfx_index,
)
from app.services.video_builder import FFMPEG, FFPROBE  # noqa: E402

AUTOMATION_DIR = Path(__file__).resolve().parent
EXPORT_DIR = AUTOMATION_DIR / "export"
BEAT_ORDER = ["HOOK", "VẤN ĐỀ", "BỐI CẢNH", "GIẢI PHÁP", "HƯỚNG DẪN", "VÍ DỤ", "KẾT QUẢ", "CTA"]
LANGS = ["vi-VN", "en-US"]


def _probe_duration(path: Path) -> float:
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def _compute_visible_scenes(lang: str, scenes_by_beat: dict[str, list[int]], raw_dur_of: dict[int, float]):
    """Tính (scene_n, abs_start_trong_toan_video, do_dai_thuc_su_hien_thi) cho
    TỪNG cảnh, dựa trên độ dài THẬT của từng đoạn đã dựng (build/scene_XX.mp4)
    — có thể bị CẮT NGẮN (giọng đọc ngắn hơn tổng Flow) hoặc LẶP LẠI (giọng
    đọc dài hơn, video tự lặp từ đầu) so với thời lượng gốc trong storyboard."""
    build_dir = EXPORT_DIR / lang / "build"
    beat_final_durs = [_probe_duration(build_dir / f"scene_{i:02d}.mp4") for i in range(1, len(BEAT_ORDER) + 1)]

    visible: list[tuple[int, float, float]] = []
    cum_beat_offset = 0.0
    for bi, beat in enumerate(BEAT_ORDER):
        final_dur = beat_final_durs[bi]
        cum_in_beat = 0.0
        for scene_n in scenes_by_beat[beat]:
            raw_d = raw_dur_of[scene_n]
            remaining = final_dur - cum_in_beat
            if remaining <= 0:
                break  # cảnh này và mọi cảnh sau nó trong đoạn bị cắt mất hoàn toàn
            visible_d = min(raw_d, remaining)
            if visible_d > 0.05:
                visible.append((scene_n, cum_beat_offset + cum_in_beat, visible_d))
            cum_in_beat += raw_d
        cum_beat_offset += final_dur
    return visible, beat_final_durs


def main() -> None:
    scenes = json.loads((AUTOMATION_DIR / "scene_prompts_final.json").read_text(encoding="utf-8"))
    windows = json.loads((AUTOMATION_DIR / "scene_windows.json").read_text(encoding="utf-8"))
    beat_of = {w["scene_n"]: w["text"].split("\n", 1)[0].strip() for w in windows}
    prompt_of = {s["scene_n"]: s["prompt"] for s in scenes}
    raw_dur_of = {s["scene_n"]: s["end"] - s["start"] for s in scenes}

    scenes_by_beat: dict[str, list[int]] = {b: [] for b in BEAT_ORDER}
    for s in scenes:
        scenes_by_beat[beat_of[s["scene_n"]]].append(s["scene_n"])
    for b in scenes_by_beat:
        scenes_by_beat[b].sort()

    visible_by_lang: dict[str, list[tuple[int, float, float]]] = {}
    for lang in LANGS:
        visible, beat_durs = _compute_visible_scenes(lang, scenes_by_beat, raw_dur_of)
        visible_by_lang[lang] = visible
        print(f"[regen][{lang}] {len(visible)}/{len(scenes)} cảnh thực sự lên hình. "
              f"Độ dài từng đoạn: {[round(d, 2) for d in beat_durs]}")

    all_visible_scene_ns = sorted({sn for lang in LANGS for sn, _, _ in visible_by_lang[lang]})
    invisible = sorted(set(prompt_of) - set(all_visible_scene_ns))
    print(f"[regen] Tổng {len(all_visible_scene_ns)}/{len(scenes)} cảnh lên hình ở ÍT NHẤT 1 ngôn ngữ.")
    if invisible:
        print(f"[regen] CẢNH KHÔNG BAO GIỜ LÊN HÌNH (cả 2 ngôn ngữ): {invisible}")

    cache_path = AUTOMATION_DIR / "sfx_layer_cache.json"
    layer_suggestions: dict[int, list[dict]] = {}
    if cache_path.exists():
        layer_suggestions = {int(k): v for k, v in json.loads(cache_path.read_text(encoding="utf-8")).items()}
        print(f"[regen] Đã có cache {len(layer_suggestions)} cảnh từ lần chạy trước — bỏ qua, chỉ làm phần còn thiếu.")

    print("[regen] Nhờ Claude đề xuất lớp âm thanh cho từng cảnh thực sự hiển thị...")
    for sn in all_visible_scene_ns:
        if layer_suggestions.get(sn):  # đã có kết quả (không rỗng) từ lần chạy trước -> bỏ qua
            continue
        layers = suggest_sfx_layers(prompt_of[sn])
        layer_suggestions[sn] = layers
        queries = [l.get("query_vi") for l in layers]
        print(f"    cảnh {sn:02d}: {len(layers)} lớp -> {queries}")
        cache_path.write_text(
            json.dumps({str(k): v for k, v in layer_suggestions.items()}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print("[regen] Tải danh sách hiệu ứng âm thanh gốc từ tiengdong.com (dùng chung cho cả 2 ngôn ngữ)...")
    sfx_index = build_sfx_index()
    print(f"[regen] Có {len(sfx_index)} hiệu ứng trong danh mục.")

    for lang in LANGS:
        out_title_check = EXPORT_DIR / lang / "final_with_title_v2.mp4"
        if out_title_check.exists():
            print(f"[regen][{lang}] Đã có sẵn {out_title_check} từ lần chạy trước — bỏ qua.")
            continue

        plans: list[ScenePlan] = []
        for sn, abs_start, visible_d in visible_by_lang[lang]:
            raw_layers = layer_suggestions.get(sn, [])
            layers = [
                SfxLayer(
                    query_vi=str(rl.get("query_vi", "")).strip(),
                    gain_db=float(rl.get("gain_db", -8.0)),
                    start_offset=float(rl.get("start_offset", 0.0) or 0.0),
                    duration=(float(rl["duration"]) if rl.get("duration") is not None else None),
                    allow_birds=bool(rl.get("allow_birds", False)),
                )
                for rl in raw_layers
                if rl.get("query_vi")
            ]
            plans.append(ScenePlan(scene_n=sn, start_sec=abs_start, duration_sec=visible_d, layers=layers))

        workdir = EXPORT_DIR / lang / "sfx_v2"
        out_sfx = EXPORT_DIR / lang / "final_with_sfx_v2.mp4"
        print(f"[regen][{lang}] Đang hoà {sum(len(p.layers) for p in plans)} lớp âm thanh vào video...")
        apply_step13_sfx(
            EXPORT_DIR / lang / "final.mp4", plans, out_sfx, workdir, index=sfx_index,
        )
        print(f"[regen][{lang}] Xong -> {out_sfx}")

        poster_name = "poster_vi.mp4" if lang == "vi-VN" else "poster_en.mp4"
        concat_txt = EXPORT_DIR / lang / "_title_concat_v2.txt"
        concat_txt.write_text(
            f"file '../title_cards/{poster_name}'\nfile 'final_with_sfx_v2.mp4'\n", encoding="utf-8"
        )
        out_title = EXPORT_DIR / lang / "final_with_title_v2.mp4"
        subprocess.run(
            [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_txt), "-c", "copy", str(out_title)],
            check=True, capture_output=True,
        )
        concat_txt.unlink()
        print(f"[regen][{lang}] Video hoàn chỉnh (có tiêu đề) -> {out_title}")

    print("[regen] XONG CẢ 2 NGÔN NGỮ.")


if __name__ == "__main__":
    main()
