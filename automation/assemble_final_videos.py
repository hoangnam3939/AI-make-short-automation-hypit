"""Bước 10-13 thật: sau khi 37 cảnh Flow đã tải xong (run_real_generation.py),
gộp lại thành video hoàn chỉnh CHO CẢ 2 NGÔN NGỮ (Việt + English), rồi thêm
hiệu ứng âm thanh (Bước 13) vào từng bản.

Cách gộp: 37 cảnh Flow (mỗi cảnh ~8s, KHÔNG có lời dẫn riêng) được nhóm lại
theo đúng 8 đoạn lời dẫn (script_quang_trung.txt) — vd cảnh 1-2 thuộc đoạn
HOOK, cảnh 3-6 thuộc VẤN ĐỀ... (xem scene_windows.json). Với mỗi đoạn: nối các
cảnh con lại thành 1 clip (concat_scenes), rồi build_scene() sẽ tự lặp/cắt clip
đó cho khớp đúng độ dài giọng đọc của đoạn — đúng kỹ thuật đã có ở
video_builder.py, không cần code ghép thời lượng mới.
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

from app.services.multilang_export import export_multi_language  # noqa: E402
from app.services.sfx_sourcing import apply_step13_sfx, build_sfx_index  # noqa: E402
from app.services.video_builder import FFPROBE, concat_scenes  # noqa: E402

AUTOMATION_DIR = Path(__file__).resolve().parent
DOWNLOADS_DIR = AUTOMATION_DIR / "downloads"
EXPORT_DIR = AUTOMATION_DIR / "export"

BEAT_ORDER = ["HOOK", "VẤN ĐỀ", "BỐI CẢNH", "GIẢI PHÁP", "HƯỚNG DẪN", "VÍ DỤ", "KẾT QUẢ", "CTA"]

# Từ khóa tìm hiệu ứng âm thanh (Bước 13) phù hợp với không khí từng đoạn.
BEAT_SFX_QUERY = {
    "HOOK": "tiệc rượu pháo hoa đêm giao thừa",
    "VẤN ĐỀ": "quân đội hành quân biên giới trống trận",
    "BỐI CẢNH": "căng thẳng nghiêm trọng quyết định",
    "GIẢI PHÁP": "bí mật ban đêm căng thẳng",
    "HƯỚNG DẪN": "bước chân hành quân thần tốc trống trận",
    "VÍ DỤ": "trận đánh gươm giáo hỗn loạn chiến đấu",
    "KẾT QUẢ": "hoảng loạn chạy trốn ngựa phi",
    "CTA": "hào hùng chiến thắng",
}


def _parse_script_beats(path: Path) -> dict[str, str]:
    beats: dict[str, str] = {}
    cur_label = None
    cur_lines: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\[\d{2}:\d{2}-\d{2}:\d{2}\]\s*(.+)$", line.strip())
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


def _probe_duration(path: Path) -> float:
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def main() -> None:
    windows = json.loads((AUTOMATION_DIR / "scene_windows.json").read_text(encoding="utf-8"))
    progress = json.loads((AUTOMATION_DIR / "generation_progress.json").read_text(encoding="utf-8"))

    # Nhóm scene_n theo đúng thứ tự 8 đoạn lời dẫn.
    beat_scenes: dict[str, list[int]] = {b: [] for b in BEAT_ORDER}
    for w in windows:
        label = w["text"].split("\n", 1)[0].strip()
        beat_scenes[label].append(w["scene_n"])

    missing = [n for scenes in beat_scenes.values() for n in scenes
               if progress.get(str(n), {}).get("status") != "done"]
    if missing:
        raise RuntimeError(
            f"Còn {len(missing)} cảnh chưa tạo xong (scene {missing}) — "
            "chạy xong run_real_generation.py hết rồi mới chạy file này."
        )

    beat_clip_paths: list[Path] = []
    for beat in BEAT_ORDER:
        scene_ns = beat_scenes[beat]
        clip_paths = [Path(progress[str(n)]["path"]) for n in scene_ns]
        out_path = EXPORT_DIR / "beat_clips" / f"{beat}.mp4"
        if len(clip_paths) == 1:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(clip_paths[0].read_bytes())
        else:
            concat_scenes(clip_paths, out_path)
        beat_clip_paths.append(out_path)
        print(f"[assemble] Đoạn '{beat}': gộp {len(clip_paths)} cảnh -> {out_path}")

    vi_beats = _parse_script_beats(AUTOMATION_DIR / "script_quang_trung.txt")
    en_beats = _parse_script_beats(AUTOMATION_DIR / "script_quang_trung_en.txt")
    beats_text_by_lang = {
        "vi-VN": [vi_beats[b] for b in BEAT_ORDER],
        "en-US": [en_beats[b] for b in BEAT_ORDER],
    }

    print("[assemble] Dựng giọng đọc + ghép video cho cả 2 ngôn ngữ (batch)...")
    results = asyncio.run(
        export_multi_language(
            ["vi-VN", "en-US"], beats_text_by_lang, beat_clip_paths,
            workdir=EXPORT_DIR, mode="batch", format_="long",
        )
    )
    result_by_lang = {r.language_code: r for r in results}
    print("[assemble] Đã có video (chưa SFX):", {k: str(v.final_video_path) for k, v in result_by_lang.items()})

    print("[assemble] Tải danh sách hiệu ứng âm thanh (Bước 13) từ tiengdong.com...")
    sfx_index = build_sfx_index()

    for lang, result in result_by_lang.items():
        build_dir = EXPORT_DIR / lang / "build"
        offsets: list[float] = []
        t = 0.0
        for i in range(1, len(BEAT_ORDER) + 1):
            offsets.append(t)
            t += _probe_duration(build_dir / f"scene_{i:02d}.mp4")

        durations = [_probe_duration(build_dir / f"scene_{i:02d}.mp4") for i in range(1, len(BEAT_ORDER) + 1)]
        scenes_for_sfx = [
            (i + 1, offsets[i], durations[i], BEAT_SFX_QUERY[BEAT_ORDER[i]])
            for i in range(len(BEAT_ORDER))
        ]
        final_with_sfx = EXPORT_DIR / lang / "final_with_sfx.mp4"
        apply_step13_sfx(
            result.final_video_path, scenes_for_sfx, final_with_sfx,
            workdir=EXPORT_DIR / lang / "sfx", index=sfx_index,
        )
        print(f"[assemble] [{lang}] Video hoàn chỉnh + SFX -> {final_with_sfx}")

    print("[assemble] XONG CẢ 2 NGÔN NGỮ.")


if __name__ == "__main__":
    main()
