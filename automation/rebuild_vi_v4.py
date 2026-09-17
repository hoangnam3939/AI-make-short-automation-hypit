"""V4: dựng lại TOÀN BỘ 8 đoạn bản tiếng Việt bằng build_scene() đã sửa
(video_builder.py) — target_dur = max(giọng đọc, video gốc), KHÔNG còn cắt
mất cảnh nào nữa dù giọng đọc ngắn hơn tổng độ dài Flow đã tạo. Dùng lại
đúng giọng đọc đã có (audio/ cho 5 đoạn không đổi, audio_v3/ cho 3 đoạn đã
sửa lời dẫn), video gốc từ beat_clips/, rồi chạy lại Bước 13 (SFX từng cảnh,
tái dùng cache gợi ý) cho ra bản V4."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from app.services.sfx_sourcing import ScenePlan, SfxLayer, apply_step13_sfx, build_sfx_index  # noqa: E402
from app.services.video_builder import FFMPEG, FFPROBE, build_scene, concat_scenes  # noqa: E402

AUTOMATION_DIR = Path(__file__).resolve().parent
EXPORT_DIR = AUTOMATION_DIR / "export"
LANG = "vi-VN"
BEAT_ORDER = ["HOOK", "VẤN ĐỀ", "BỐI CẢNH", "GIẢI PHÁP", "HƯỚNG DẪN", "VÍ DỤ", "KẾT QUẢ", "CTA"]
CHANGED_BEATS = {"BỐI CẢNH", "GIẢI PHÁP", "HƯỚNG DẪN"}


def _probe_duration(path: Path) -> float:
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def main() -> None:
    lang_dir = EXPORT_DIR / LANG
    build_v4_dir = lang_dir / "build_v4"
    build_v4_dir.mkdir(parents=True, exist_ok=True)

    print("[v4] Dựng lại cả 8 đoạn bằng build_scene() đã sửa (khong con cat mat canh)...")
    for i, beat in enumerate(BEAT_ORDER, start=1):
        audio_dir = "audio_v3" if beat in CHANGED_BEATS else "audio"
        audio_path = lang_dir / audio_dir / f"scene_{i:02d}.mp3"
        beat_clip = EXPORT_DIR / "beat_clips" / f"{beat}.mp4"
        scene_out = build_v4_dir / f"scene_{i:02d}.mp4"
        audio_dur = _probe_duration(audio_path)
        video_dur = _probe_duration(beat_clip)
        build_scene(audio_path, scene_out, video_path=beat_clip, format_="long")
        new_dur = _probe_duration(scene_out)
        print(f"    [{i:02d}] {beat}: giọng đọc {audio_dur:.2f}s, video gốc {video_dur:.2f}s -> đoạn dựng {new_dur:.2f}s")

    print("[v4] Ghép lại 8 đoạn thành final_v4.mp4...")
    scene_paths = [build_v4_dir / f"scene_{i:02d}.mp4" for i in range(1, len(BEAT_ORDER) + 1)]
    final_v4 = concat_scenes(scene_paths, lang_dir / "final_v4.mp4")
    print(f"[v4] -> {final_v4}")

    print("[v4] Tính lại cảnh thực sự hiển thị (giờ phải đủ 34/34 hoặc gần đủ)...")
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

    missing = sorted(set(raw_dur_of) - {sn for sn, _, _ in visible})
    print(f"[v4] {len(visible)}/{len(scenes)} cảnh hiển thị. Độ dài từng đoạn: {[round(d,2) for d in beat_durs]}")
    if missing:
        print(f"[v4] CẢNH VẪN CHƯA HIỆN (không có Flow clip riêng / lỗi khác, không phải do cắt): {missing}")
    else:
        print("[v4] TẤT CẢ 34/34 CẢNH ĐÃ HIỂN THỊ ĐỦ.")

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

    print("[v4] Tải danh sách hiệu ứng âm thanh...")
    sfx_index = build_sfx_index()
    workdir = lang_dir / "sfx_v4"
    out_sfx = lang_dir / "final_with_sfx_v4.mp4"
    print(f"[v4] Đang hoà {sum(len(p.layers) for p in plans)} lớp âm thanh...")
    apply_step13_sfx(final_v4, plans, out_sfx, workdir, index=sfx_index)
    print(f"[v4] -> {out_sfx}")

    concat_txt = lang_dir / "_title_concat_v4.txt"
    concat_txt.write_text("file '../title_cards/poster_vi.mp4'\nfile 'final_with_sfx_v4.mp4'\n", encoding="utf-8")
    out_title = lang_dir / "final_with_title_v4.mp4"
    subprocess.run(
        [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_txt), "-c", "copy", str(out_title)],
        check=True, capture_output=True,
    )
    concat_txt.unlink()
    print(f"[v4] XONG -> {out_title}")


if __name__ == "__main__":
    main()
