"""V4 (bản sửa đúng): dựng lại TOÀN BỘ 8 đoạn bản tiếng Việt, sửa thêm 2 lỗi
mới phát hiện khi kiểm chứng V4 bản đầu:

1. Đoạn "VÍ DỤ" trong `beat_clips/` chỉ ghép được 3/9 cảnh (lỗi có sẵn từ
   trước, không phải do lần sửa này) — dựng lại đúng từ danh sách 9 cảnh
   thật trong generation_progress.json.
2. Toàn bộ phép tính "cảnh nào hiện ở giây nào" trước giờ dùng SAI độ dài kế
   hoạch trong scene_prompts_final.json (7-16 giây/cảnh) — thực tế MỌI clip
   Google Flow trả về đều dài ĐÚNG 10.005 giây bất kể yêu cầu bao nhiêu giây.
   Sửa: đo trực tiếp độ dài thật từng clip gốc (ffprobe), không dùng số liệu
   kế hoạch nữa.
"""
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
CHANGED_NARRATION_BEATS = {"BỐI CẢNH", "GIẢI PHÁP", "HƯỚNG DẪN"}


def _probe_duration(path: Path) -> float:
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def main() -> None:
    lang_dir = EXPORT_DIR / LANG
    windows = json.loads((AUTOMATION_DIR / "scene_windows.json").read_text(encoding="utf-8"))
    progress = json.loads((AUTOMATION_DIR / "generation_progress.json").read_text(encoding="utf-8"))
    beat_of = {w["scene_n"]: w["text"].split("\n", 1)[0].strip() for w in windows}

    scenes_by_beat: dict[str, list[int]] = {b: [] for b in BEAT_ORDER}
    for sn_str, entry in progress.items():
        sn = int(sn_str)
        if entry.get("status") == "done" and sn in beat_of:
            scenes_by_beat[beat_of[sn]].append(sn)
    for b in scenes_by_beat:
        scenes_by_beat[b].sort()
        print(f"[fix] Đoạn '{b}': {len(scenes_by_beat[b])} cảnh -> {scenes_by_beat[b]}")

    print("\n[fix] Đo độ dài THẬT từng clip gốc (không dùng số liệu kế hoạch)...")
    real_dur_of: dict[int, float] = {}
    clip_path_of: dict[int, Path] = {}
    for sn_str, entry in progress.items():
        sn = int(sn_str)
        if entry.get("status") != "done":
            continue
        p = Path(entry["path"])
        if not p.is_absolute():
            p = AUTOMATION_DIR.parent / p
        if not p.exists():
            # Hồ sơ ghi đường dẫn CŨ (lỗi thật: cảnh được tạo lại sau đó với
            # timestamp mới nhưng generation_progress.json không cập nhật
            # lại path) — lấy đúng file mp4 MỚI NHẤT thật sự có trong đúng
            # thư mục scene_XX trên đĩa thay vì tin mù vào hồ sơ.
            scene_dir = AUTOMATION_DIR / "downloads" / f"scene_{sn:02d}"
            candidates = sorted(scene_dir.glob("*.mp4"), key=lambda f: f.stat().st_mtime)
            if not candidates:
                print(f"    [CANH BAO] scene {sn}: khong tim thay file nao trong {scene_dir}")
                continue
            p = candidates[-1]
        clip_path_of[sn] = p
        real_dur_of[sn] = _probe_duration(p)

    print("\n[fix] Dựng lại đúng đủ beat_clips (fix lỗi thiếu cảnh 'VÍ DỤ')...")
    beat_clips_dir = EXPORT_DIR / "beat_clips_fixed"
    beat_clips_dir.mkdir(parents=True, exist_ok=True)
    beat_clip_paths: dict[str, Path] = {}
    for beat in BEAT_ORDER:
        scene_ns = scenes_by_beat[beat]
        clip_paths = [clip_path_of[sn] for sn in scene_ns]
        out_path = beat_clips_dir / f"{beat}.mp4"
        if len(clip_paths) == 1:
            out_path.write_bytes(clip_paths[0].read_bytes())
        else:
            concat_scenes(clip_paths, out_path)
        beat_clip_paths[beat] = out_path
        expected = sum(real_dur_of[sn] for sn in scene_ns)
        actual = _probe_duration(out_path)
        print(f"    {beat}: {len(scene_ns)} cảnh, dự kiến {expected:.2f}s, thực tế {actual:.2f}s")

    build_v4_dir = lang_dir / "build_v4_fixed"
    build_v4_dir.mkdir(parents=True, exist_ok=True)

    print("\n[fix] Dựng lại cả 8 đoạn (video đầy đủ, giọng đọc không làm mất cảnh)...")
    for i, beat in enumerate(BEAT_ORDER, start=1):
        audio_dir = "audio_v3" if beat in CHANGED_NARRATION_BEATS else "audio"
        audio_path = lang_dir / audio_dir / f"scene_{i:02d}.mp3"
        scene_out = build_v4_dir / f"scene_{i:02d}.mp4"
        build_scene(audio_path, scene_out, video_path=beat_clip_paths[beat], format_="long")
        print(f"    [{i:02d}] {beat}: -> {_probe_duration(scene_out):.2f}s")

    print("\n[fix] Ghép lại 8 đoạn...")
    scene_paths = [build_v4_dir / f"scene_{i:02d}.mp4" for i in range(1, len(BEAT_ORDER) + 1)]
    final_v4 = concat_scenes(scene_paths, lang_dir / "final_v4_fixed.mp4")
    print(f"[fix] -> {final_v4}")

    print("\n[fix] Tính lại cảnh thực sự hiển thị (dùng độ dài THẬT từng clip)...")
    beat_durs = [_probe_duration(p) for p in scene_paths]
    visible: list[tuple[int, float, float]] = []
    cum_beat_offset = 0.0
    for bi, beat in enumerate(BEAT_ORDER):
        final_dur = beat_durs[bi]
        cum_in_beat = 0.0
        for scene_n in scenes_by_beat[beat]:
            raw_d = real_dur_of[scene_n]
            remaining = final_dur - cum_in_beat
            if remaining <= 0:
                break
            visible_d = min(raw_d, remaining)
            if visible_d > 0.05:
                visible.append((scene_n, cum_beat_offset + cum_in_beat, visible_d))
            cum_in_beat += raw_d
        cum_beat_offset += final_dur

    total_scenes = len(real_dur_of)
    missing = sorted(set(real_dur_of) - {sn for sn, _, _ in visible})
    print(f"[fix] {len(visible)}/{total_scenes} cảnh hiển thị. Độ dài từng đoạn: {[round(d,2) for d in beat_durs]}")
    if missing:
        print(f"[fix] CẢNH VẪN THIẾU: {missing}")
    else:
        print(f"[fix] TẤT CẢ {total_scenes}/{total_scenes} CẢNH ĐÃ HIỂN THỊ ĐỦ.")

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

    print("\n[fix] Tải danh sách hiệu ứng âm thanh...")
    sfx_index = build_sfx_index()
    workdir = lang_dir / "sfx_v4_fixed"
    out_sfx = lang_dir / "final_with_sfx_v4.mp4"
    print(f"[fix] Đang hoà {sum(len(p.layers) for p in plans)} lớp âm thanh...")
    apply_step13_sfx(final_v4, plans, out_sfx, workdir, index=sfx_index)
    print(f"[fix] -> {out_sfx}")

    concat_txt = lang_dir / "_title_concat_v4fixed.txt"
    concat_txt.write_text("file '../title_cards/poster_vi.mp4'\nfile 'final_with_sfx_v4.mp4'\n", encoding="utf-8")
    out_title = lang_dir / "final_with_title_v4.mp4"
    subprocess.run(
        [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_txt), "-c", "copy", str(out_title)],
        check=True, capture_output=True,
    )
    concat_txt.unlink()
    print(f"\n[fix] XONG -> {out_title}")


if __name__ == "__main__":
    main()
