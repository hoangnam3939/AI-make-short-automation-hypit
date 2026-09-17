import asyncio
import subprocess
from pathlib import Path

import pytest

from app.services.video_builder import (
    FFPROBE,
    build_scene,
    concat_scenes,
    generate_narration,
)


def _probe(path: Path) -> dict:
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height",
         "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    result = {}
    for line in out.stdout.strip().splitlines():
        k, v = line.split("=")
        result[k] = v
    return result


def test_end_to_end_two_scene_video(tmp_path):
    """Test đầu-cuối thật: sinh giọng đọc (edge-tts) -> dựng 2 cảnh placeholder ->
    ghép thành 1 video hoàn chỉnh. Không cần API key AI."""

    audio1 = tmp_path / "audio" / "scene_01.mp3"
    audio2 = tmp_path / "audio" / "scene_02.mp3"
    asyncio.run(generate_narration("Đây là cảnh một, kiểm tra hệ thống.", "vi-VN", audio1))
    asyncio.run(generate_narration("Đây là cảnh hai, kiểm tra hệ thống.", "vi-VN", audio2))
    assert audio1.exists() and audio1.stat().st_size > 0
    assert audio2.exists() and audio2.stat().st_size > 0

    build_dir = tmp_path / "build"
    r1 = build_scene(audio1, build_dir / "scene_01.mp4", video_path=None, format_="long")
    r2 = build_scene(audio2, build_dir / "scene_02.mp4", video_path=None, format_="long")

    probe1 = _probe(r1.video_path)
    assert probe1["width"] == "1920" and probe1["height"] == "1080"

    final = concat_scenes([r1.video_path, r2.video_path], tmp_path / "output" / "final.mp4")
    assert final.exists()
    probe_final = _probe(final)
    total_expected = r1.duration_sec + r2.duration_sec
    assert abs(float(probe_final["duration"]) - total_expected) < 0.5


def test_short_format_uses_vertical_resolution(tmp_path):
    audio = tmp_path / "audio" / "scene_01.mp3"
    asyncio.run(generate_narration("Test short format.", "en-US", audio))

    out = build_scene(audio, tmp_path / "build" / "scene_01.mp4", video_path=None, format_="short")
    probe = _probe(out.video_path)
    assert probe["width"] == "1080" and probe["height"] == "1920"
