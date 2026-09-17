"""Dựng lại bản tiếng Việt V3 cho video Quang Trung: sửa 2 lỗi người dùng báo
(2026-09-13): (1) SFX lẫn tiếng "Niệm Phật" (đã sửa trong sfx_sourcing.py),
(2) lời dẫn không khớp cảnh — đã cắt các câu mô tả cảnh bị ẩn/cắt gần hết
trong script_quang_trung.txt (xem skill narration-scene-alignment).

Chỉ dựng lại 3 đoạn có văn bản thay đổi (BỐI CẢNH, GIẢI PHÁP, HƯỚNG DẪN) từ
đúng clip Flow gốc đã lưu (automation/export/beat_clips/), giữ nguyên 5 đoạn
còn lại, rồi ghép lại thành final.mp4 mới, tính lại cửa sổ cảnh THỰC SỰ hiển
thị, và chạy lại toàn bộ Bước 13 (SFX theo từng cảnh, tái dùng gợi ý đã có
trong cache) cho ra bản V3.
"""
from __future__ import annotations

import asyncio
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from app.services.sfx_sourcing import ScenePlan, SfxLayer, apply_step13_sfx, build_sfx_index  # noqa: E402
from app.services.video_builder import FFMPEG, FFPROBE, build_scene, concat_scenes, generate_narration  # noqa: E402

AUTOMATION_DIR = Path(__file__).resolve().parent
EXPORT_DIR = AUTOMATION_DIR / "export"
LANG = "vi-VN"
BEAT_ORDER = ["HOOK", "VẤN ĐỀ", "BỐI CẢNH", "GIẢI PHÁP", "HƯỚNG DẪN", "VÍ DỤ", "KẾT QUẢ", "CTA"]
CHANGED_BEATS = {"BỐI CẢNH", "GIẢI PHÁP", "HƯỚNG DẪN"}
_TIMESTAMP_RE = re.compile(r"\[\d{2}:\d{2}-\d{2}:\d{2}\]\s*(.+)")


def _probe_duration(path: Path) -> float:
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def _parse_script_beats(path: Path) -> dict[str, str]:
    beats: dict[str, str] = {}
    cur_label = None
    cur_lines: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _TIMESTAMP_RE.match(line.strip())
        if m:
            if cur_label:
                beats[cur_label] = " ".join(cur_lines).strip()
            cur_label = m.group(1).strip()
            cur_lines = []
        elif line.strip() and cur_label:
            cur_lines.append(line.strip())
    if cur_label:
        beats[cur_label] = " ".join(cur_lines).strip()
    return beats


def main() -> None:
    lang_dir = EXPORT_DIR / LANG
    beats_text = _parse_script_beats(AUTOMATION_DIR / "script_quang_trung.txt")

    print("[v3] Dựng lại 3 đoạn có lời dẫn thay đổi...")
    for i, beat in enumerate(BEAT_ORDER, start=1):
        scene_out = lang_dir / "build" / f"scene_{i:02d}.mp4"
        if beat not in CHANGED_BEATS:
            print(f"    [{i:02d}] {beat}: giữ nguyên (không đổi lời dẫn)")
            continue
        audio_path = lang_dir / "audio_v3" / f"scene_{i:02d}.mp3"
        beat_clip = EXPORT_DIR / "beat_clips" / f"{beat}.mp4"
        asyncio.run(generate_narration(beats_text[beat], LANG, audio_path))
        new_dur = _probe_duration(audio_path)
        old_dur = _probe_duration(scene_out)
        build_scene(audio_path, scene_out, video_path=beat_clip, format_="long")
        print(f"    [{i:02d}] {beat}: giọng đọc {old_dur:.2f}s -> {new_dur:.2f}s, đã dựng lại")

    print("[v3] Ghép lại 8 đoạn thành final_v3.mp4...")
    scene_paths = [lang_dir / "build" / f"scene_{i:02d}.mp4" for i in range(1, len(BEAT_ORDER) + 1)]
    final_v3 = concat_scenes(scene_paths, lang_dir / "final_v3.mp4")
    print(f"[v3] -> {final_v3}")

    print("[v3] Tính lại cảnh THỰC SỰ hiển thị (độ dài đoạn đã đổi)...")
    scenes = json.loads((AUTOMATION_DIR / "scene_prompts_final.json").read_text(encoding="utf-8"))
    windows = json.loads((AUTOMATION_DIR / "scene_windows.json").read_text(encoding="utf-8"))
    beat_of = {w["scene_n"]: w["text"].split("\n", 1)[0].strip() for w in windows}
    raw_dur_of = {s["scene_n"]: s["end"] - s["start"] for s in scenes}
    scenes_by_beat: dict[str, list[int]] = {b: [] for b in BEAT_ORDER}
    for s in scenes:
        scenes_by_beat[beat_of[s["scene_n"]]].append(s["scene_n"])
    for b in scenes_by_beat:
        scenes_by_beat[b].sort()

    beat_durs = [_probe_duration(p) for p in scene_paths]
    visible: list[tuple[int, float, float]] = []
    cum_beat_offset = 0.0
    for bi, beat in enumerate(BEAT_ORDER):
        final_dur = beat_durs[bi]
        cum_in_beat = 0.0
        for scene_n in scenes_by_beat[beat]:
            raw_d = raw_dur_of[scene_n]
            remaining = final_dur - cum_in_beat
            if remaining <= 0:
                break
            visible_d = min(raw_d, remaining)
            if visible_d > 0.05:
                visible.append((scene_n, cum_beat_offset + cum_in_beat, visible_d))
            cum_in_beat += raw_d
        cum_beat_offset += final_dur
    print(f"[v3] {len(visible)}/{len(scenes)} cảnh hiển thị. Độ dài từng đoạn: {[round(d,2) for d in beat_durs]}")

    cache_path = AUTOMATION_DIR / "sfx_layer_cache.json"
    layer_suggestions = {int(k): v for k, v in json.loads(cache_path.read_text(encoding="utf-8")).items()}

    plans: list[ScenePlan] = []
    for sn, abs_start, visible_d in visible:
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

    print("[v3] Tải danh sách hiệu ứng âm thanh (đã loại 'Niệm Phật')...")
    sfx_index = build_sfx_index()
    workdir = lang_dir / "sfx_v3"
    out_sfx = lang_dir / "final_with_sfx_v3.mp4"
    print(f"[v3] Đang hoà {sum(len(p.layers) for p in plans)} lớp âm thanh...")
    apply_step13_sfx(final_v3, plans, out_sfx, workdir, index=sfx_index)
    print(f"[v3] -> {out_sfx}")

    concat_txt = lang_dir / "_title_concat_v3.txt"
    concat_txt.write_text("file '../title_cards/poster_vi.mp4'\nfile 'final_with_sfx_v3.mp4'\n", encoding="utf-8")
    out_title = lang_dir / "final_with_title_v3.mp4"
    subprocess.run(
        [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_txt), "-c", "copy", str(out_title)],
        check=True, capture_output=True,
    )
    concat_txt.unlink()
    print(f"[v3] XONG -> {out_title}")


if __name__ == "__main__":
    main()
