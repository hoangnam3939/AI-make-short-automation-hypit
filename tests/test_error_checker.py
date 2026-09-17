"""Test THẬT (không mock) — dùng ffmpeg dựng các clip lavfi có lỗi đã biết
trước (sai độ phân giải, sai fps, có đoạn đen, có đoạn đứng hình) để xác
minh error_checker phát hiện đúng, không báo giả."""
import subprocess
from pathlib import Path

import pytest

from app.services.video_builder import FFMPEG
from app.services import error_checker as ec


def _make_clip(out_path: Path, width: int, height: int, fps: int, duration: float, color: str = "red") -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        FFMPEG, "-y",
        "-f", "lavfi", "-i", f"color=c={color}:s={width}x{height}:d={duration}:r={fps}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(out_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path


@pytest.fixture(scope="module")
def clip_1920x1080_24fps(tmp_path_factory):
    d = tmp_path_factory.mktemp("clips")
    return _make_clip(d / "ok.mp4", 1920, 1080, 24, 2)


@pytest.fixture(scope="module")
def clip_wrong_resolution_and_fps(tmp_path_factory):
    d = tmp_path_factory.mktemp("clips2")
    return _make_clip(d / "bad.mp4", 640, 360, 15, 2)


@pytest.fixture(scope="module")
def clip_all_black(tmp_path_factory):
    d = tmp_path_factory.mktemp("clips3")
    return _make_clip(d / "black.mp4", 640, 360, 24, 2, color="black")


@pytest.fixture(scope="module")
def clip_frozen(tmp_path_factory):
    # mau tinh, khong nhieu -> toan bo la 1 khung hinh dung yen
    d = tmp_path_factory.mktemp("clips4")
    return _make_clip(d / "frozen.mp4", 640, 360, 24, 3, color="blue")


def test_probe_video_stream_reads_correct_dimensions_and_fps(clip_1920x1080_24fps):
    info = ec.probe_video_stream(clip_1920x1080_24fps)
    assert info.width == 1920 and info.height == 1080
    assert abs(info.fps - 24.0) < 0.1
    assert 1.5 < info.duration < 2.5


def test_check_resolution_and_fps_consistency_passes_for_matching_clip(clip_1920x1080_24fps):
    issues = ec.check_resolution_and_fps_consistency(
        [clip_1920x1080_24fps], expected_width=1920, expected_height=1080, expected_fps=24,
    )
    assert issues == []


def test_check_resolution_and_fps_consistency_flags_mismatch(clip_wrong_resolution_and_fps):
    issues = ec.check_resolution_and_fps_consistency(
        [clip_wrong_resolution_and_fps], expected_width=1920, expected_height=1080, expected_fps=24,
    )
    assert len(issues) == 1
    assert any("Độ phân giải" in i for i in issues[0].issues)
    assert any("FPS" in i for i in issues[0].issues)


def test_check_audio_video_duration_match_flags_large_diff(clip_1920x1080_24fps):
    # clip dai ~2s, audio goc 5s -> lech qua nguong 0.6s
    msg = ec.check_audio_video_duration_match(clip_1920x1080_24fps, audio_duration_sec=5.0, tolerance_sec=0.6)
    assert msg is not None
    assert "lệch" in msg


def test_check_audio_video_duration_match_passes_within_tolerance(clip_1920x1080_24fps):
    msg = ec.check_audio_video_duration_match(clip_1920x1080_24fps, audio_duration_sec=2.0, tolerance_sec=0.6)
    assert msg is None


def test_detect_black_frames_finds_black_segment(clip_all_black):
    intervals = ec.detect_black_frames(clip_all_black, min_black_duration=1.0)
    assert len(intervals) >= 1
    start, end = intervals[0]
    assert end - start >= 1.0


def test_detect_black_frames_none_for_normal_colored_clip(clip_1920x1080_24fps):
    intervals = ec.detect_black_frames(clip_1920x1080_24fps, min_black_duration=1.0)
    assert intervals == []


def test_detect_frozen_frames_finds_static_segment(clip_frozen):
    starts = ec.detect_frozen_frames(clip_frozen, min_freeze_duration=2.0)
    assert len(starts) >= 1


def test_check_narration_scene_drift_flags_large_deviation(clip_1920x1080_24fps):
    # clip thật dài ~2s, dự kiến 5s -> lệch 60% > ngưỡng mặc định 50%.
    warnings = ec.check_narration_scene_drift([clip_1920x1080_24fps], [5.0])
    assert len(warnings) == 1
    assert "lệch" in warnings[0]
    assert "Đoạn 1" in warnings[0]


def test_check_narration_scene_drift_passes_within_tolerance(clip_1920x1080_24fps):
    warnings = ec.check_narration_scene_drift([clip_1920x1080_24fps], [2.0])
    assert warnings == []


def test_check_narration_scene_drift_ignores_zero_or_negative_planned(clip_1920x1080_24fps):
    warnings = ec.check_narration_scene_drift([clip_1920x1080_24fps], [0.0])
    assert warnings == []


def test_check_narration_scene_drift_handles_multiple_segments(clip_1920x1080_24fps, clip_wrong_resolution_and_fps):
    warnings = ec.check_narration_scene_drift(
        [clip_1920x1080_24fps, clip_wrong_resolution_and_fps], [2.0, 100.0],
    )
    assert len(warnings) == 1
    assert "Đoạn 2" in warnings[0]


def test_check_poster_text_without_tesseract_returns_clear_warning(monkeypatch, tmp_path):
    monkeypatch.setattr(ec, "_TESSERACT", None)
    fake_poster = tmp_path / "poster.png"
    fake_poster.write_bytes(b"not a real png, doesn't matter, function returns before reading it")
    warnings = ec.check_poster_text(fake_poster, "Tiêu đề bất kỳ", "Phụ đề bất kỳ")
    assert len(warnings) == 1
    assert "Tesseract" in warnings[0]


@pytest.mark.skipif(ec._TESSERACT is None, reason="Máy này chưa cài Tesseract-OCR")
def test_check_poster_text_passes_for_matching_text(tmp_path):
    from app.services.video_builder import generate_title_card_image

    poster = generate_title_card_image("VIDEO KIEM TRA", tmp_path / "poster.png", format_="long")
    warnings = ec.check_poster_text(poster, "VIDEO KIEM TRA")
    assert warnings == []


@pytest.mark.skipif(ec._TESSERACT is None, reason="Máy này chưa cài Tesseract-OCR")
def test_check_poster_text_flags_mismatch(tmp_path):
    from app.services.video_builder import generate_title_card_image

    poster = generate_title_card_image("VIDEO KIEM TRA", tmp_path / "poster.png", format_="long")
    warnings = ec.check_poster_text(poster, "MOT TIEU DE HOAN TOAN KHAC XA VOI POSTER")
    assert len(warnings) == 1
    assert "tiêu đề" in warnings[0]
