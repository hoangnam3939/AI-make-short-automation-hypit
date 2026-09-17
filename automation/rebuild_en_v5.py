"""V5 bản tiếng Anh: áp dụng đúng 2 lỗi đã sửa cho bản tiếng Việt —
(1) build_scene() không còn cắt mất cảnh (video_builder.py đã sửa),
(2) SFX theo từng cảnh, nhiều lớp, tái dùng cache gợi ý (nội dung hình ảnh
không đổi theo ngôn ngữ nên dùng chung được).

Dùng lại beat_clips_fixed/ (video gốc ĐỦ CẢNH, đã sửa 1 lần dùng chung cho
mọi ngôn ngữ) + giọng đọc tiếng Anh gốc (chưa cần sửa lời dẫn vì chưa có
phản hồi lỗi khớp cảnh riêng cho bản tiếng Anh — chỉ sửa lỗi mất cảnh + SFX)."""
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
LANG = "en-US"
BEAT_ORDER = ["HOOK", "VẤN ĐỀ", "BỐI CẢNH", "GIẢI PHÁP", "HƯỚNG DẪN", "VÍ DỤ", "KẾT QUẢ", "CTA"]


def _probe_duration(path: Path) -> float:
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def main() -> None:
    lang_dir = EXPORT_DIR / LANG
    beat_clips_dir = EXPORT_DIR / "beat_clips_fixed"
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

    print("[en] Đo độ dài thật từng clip gốc...")
    real_dur_of: dict[int, float] = {}
    for sn_str, entry in progress.items():
        sn = int(sn_str)
        if entry.get("status") != "done":
            continue
        p = Path(entry["path"])
        if not p.is_absolute():
            p = AUTOMATION_DIR.parent / p
        if not p.exists():
            scene_dir = AUTOMATION_DIR / "downloads" / f"scene_{sn:02d}"
            candidates = sorted(scene_dir.glob("*.mp4"), key=lambda f: f.stat().st_mtime)
            if not candidates:
                continue
            p = candidates[-1]
        real_dur_of[sn] = _probe_duration(p)

    build_v5_dir = lang_dir / "build_v5"
    build_v5_dir.mkdir(parents=True, exist_ok=True)

    print("[en] Dựng lại cả 8 đoạn (video đầy đủ, không mất cảnh)...")
    for i, beat in enumerate(BEAT_ORDER, start=1):
        audio_path = lang_dir / "audio" / f"scene_{i:02d}.mp3"
        beat_clip = beat_clips_dir / f"{beat}.mp4"
        scene_out = build_v5_dir / f"scene_{i:02d}.mp4"
        build_scene(audio_path, scene_out, video_path=beat_clip, format_="long")
        print(f"    [{i:02d}] {beat}: -> {_probe_duration(scene_out):.2f}s")

    print("[en] Ghép lại 8 đoạn...")
    scene_paths = [build_v5_dir / f"scene_{i:02d}.mp4" for i in range(1, len(BEAT_ORDER) + 1)]
    final_v5 = concat_scenes(scene_paths, lang_dir / "final_v5.mp4")
    print(f"[en] -> {final_v5}")

    print("[en] Tính lại cảnh thực sự hiển thị...")
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
    print(f"[en] {len(visible)}/{total_scenes} cảnh hiển thị. Độ dài từng đoạn: {[round(d,2) for d in beat_durs]}")
    if missing:
        print(f"[en] CẢNH VẪN THIẾU: {missing}")
    else:
        print(f"[en] TẤT CẢ {total_scenes}/{total_scenes} CẢNH ĐÃ HIỂN THỊ ĐỦ.")

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

    print("[en] Tải danh sách hiệu ứng âm thanh...")
    sfx_index = build_sfx_index()
    workdir = lang_dir / "sfx_v5"
    out_sfx = lang_dir / "final_with_sfx_v5.mp4"
    print(f"[en] Đang hoà {sum(len(p.layers) for p in plans)} lớp âm thanh...")
    apply_step13_sfx(final_v5, plans, out_sfx, workdir, index=sfx_index)
    print(f"[en] -> {out_sfx}")

    concat_txt = lang_dir / "_title_concat_v5.txt"
    concat_txt.write_text("file '../title_cards/poster_en.mp4'\nfile 'final_with_sfx_v5.mp4'\n", encoding="utf-8")
    out_title = lang_dir / "final_with_title_v5.mp4"
    subprocess.run(
        [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_txt), "-c", "copy", str(out_title)],
        check=True, capture_output=True,
    )
    concat_txt.unlink()
    print(f"\n[en] XONG -> {out_title}")


if __name__ == "__main__":
    main()
