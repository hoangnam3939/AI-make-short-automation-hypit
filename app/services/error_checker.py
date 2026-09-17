"""Kiểm tra lỗi (Mục 8, V3) — điểm khác biệt cạnh tranh của app, xây SAU khi
khung sườn 12 bước đã chạy được. Phần 1-4 KHÔNG cần AI — chỉ dùng ffprobe/
ffmpeg để phát hiện lỗi kỹ thuật thật trên video đã dựng:

1. Độ phân giải các cảnh không khớp định dạng đã chọn (16:9 dài / 9:16 short).
2. Khung hình/giây (fps) không khớp giữa các cảnh.
3. Thời lượng video lệch quá xa so với audio (dấu hiệu ghép sai/apad lỗi).
4. Khung hình đen (black frame) hoặc khung hình đứng yên (frozen frame) kéo
   dài bất thường — dấu hiệu clip AI lỗi hoặc placeholder bị treo.

Phần 5-6 (thêm 2026-09-15, phần CỐT LÕI/ĐỘC QUYỀN của Mục 8 — nhân vật đổi
hình dạng nằm ở character_consistency.py riêng vì cần CLIP, xem module đó):
5. Giọng đọc lệch thời gian so với kế hoạch storyboard (không dùng ffsubsync
   như đặc tả gốc gợi ý — app chưa xuất phụ đề .srt để ffsubsync có input;
   thay bằng so thời lượng thực tế/dự kiến từng đoạn, nhẹ hơn nhiều, kế thừa
   tinh thần skill narration-scene-alignment).
6. Chữ trên poster mở đầu bị lỗi hiển thị (OCR bằng Tesseract, so khớp mờ
   với tiêu đề/phụ đề dự kiến) — cần cài Tesseract-OCR (binary hệ thống,
   giống ffmpeg); máy chưa cài thì trả về 1 cảnh báo rõ ràng, KHÔNG lỗi.

Tái sử dụng đúng FFMPEG/FFPROBE đã xác nhận hoạt động ở video_builder.py.
CHỈ CẢNH BÁO, không tự chặn/tự sửa gì — 1 cảnh/đoạn lỗi không chặn cả video.
"""
from __future__ import annotations

import difflib
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from app.services.video_builder import FFMPEG, FFPROBE

_TESSERACT = shutil.which("tesseract")


@dataclass
class VideoStreamInfo:
    width: int
    height: int
    fps: float
    duration: float


@dataclass
class SceneIssues:
    scene_path: Path
    issues: list[str] = field(default_factory=list)


def probe_video_stream(path: Path) -> VideoStreamInfo:
    out = subprocess.run(
        [
            FFPROBE, "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1", str(path),
        ],
        capture_output=True, text=True, check=True,
    )
    data: dict[str, str] = {}
    for line in out.stdout.strip().splitlines():
        k, v = line.split("=", 1)
        data[k] = v

    num, den = data["r_frame_rate"].split("/")
    fps = float(num) / float(den) if float(den) != 0 else 0.0
    return VideoStreamInfo(
        width=int(data["width"]),
        height=int(data["height"]),
        fps=fps,
        duration=float(data["duration"]),
    )


def check_resolution_and_fps_consistency(
    scene_paths: list[Path],
    expected_width: int,
    expected_height: int,
    expected_fps: float = 24.0,
    fps_tolerance: float = 0.5,
) -> list[SceneIssues]:
    """Kiểm tra mọi cảnh khớp đúng độ phân giải của định dạng đã chọn và fps
    đồng nhất — lệch 1 cảnh cũng đủ làm video giật/lem khi ghép."""
    results: list[SceneIssues] = []
    for path in scene_paths:
        info = probe_video_stream(path)
        issues: list[str] = []
        if (info.width, info.height) != (expected_width, expected_height):
            issues.append(
                f"Độ phân giải {info.width}x{info.height} không khớp kỳ vọng "
                f"{expected_width}x{expected_height}"
            )
        if abs(info.fps - expected_fps) > fps_tolerance:
            issues.append(f"FPS {info.fps:.2f} lệch khỏi kỳ vọng {expected_fps}")
        if issues:
            results.append(SceneIssues(scene_path=path, issues=issues))
    return results


def check_audio_video_duration_match(
    video_path: Path, audio_duration_sec: float, tolerance_sec: float = 0.6
) -> str | None:
    """Trả về mô tả lỗi nếu thời lượng video lệch audio gốc quá tolerance_sec,
    None nếu khớp. Dấu hiệu lệch lớn thường do lỗi -shortest/apad khi dựng."""
    info = probe_video_stream(video_path)
    diff = abs(info.duration - audio_duration_sec)
    if diff > tolerance_sec:
        return (
            f"{video_path.name}: thời lượng video {info.duration:.2f}s lệch "
            f"{diff:.2f}s so với audio {audio_duration_sec:.2f}s (ngưỡng {tolerance_sec}s)"
        )
    return None


_BLACK_RE = re.compile(r"black_start:(?P<start>[\d.]+) black_end:(?P<end>[\d.]+) black_duration:(?P<dur>[\d.]+)")
_FREEZE_RE = re.compile(r"freeze_start:\s*(?P<start>[\d.]+)")


def detect_black_frames(path: Path, min_black_duration: float = 1.0, pix_threshold: float = 0.10) -> list[tuple[float, float]]:
    """Phát hiện đoạn khung hình đen kéo dài >= min_black_duration giây bằng
    ffmpeg blackdetect filter. Trả về danh sách (start, end) theo giây."""
    cmd = [
        FFMPEG, "-i", str(path),
        "-vf", f"blackdetect=d={min_black_duration}:pix_th={pix_threshold}",
        "-an", "-f", "null", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    intervals: list[tuple[float, float]] = []
    for m in _BLACK_RE.finditer(proc.stderr):
        intervals.append((float(m.group("start")), float(m.group("end"))))
    return intervals


def detect_frozen_frames(path: Path, noise_tolerance_db: str = "-60dB", min_freeze_duration: float = 2.0) -> list[float]:
    """Phát hiện đoạn khung hình đứng yên >= min_freeze_duration giây bằng
    ffmpeg freezedetect filter. Trả về danh sách thời điểm bắt đầu đứng hình."""
    cmd = [
        FFMPEG, "-i", str(path),
        "-vf", f"freezedetect=n={noise_tolerance_db}:d={min_freeze_duration}",
        "-an", "-f", "null", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    starts: list[float] = []
    for m in _FREEZE_RE.finditer(proc.stderr):
        starts.append(float(m.group("start")))
    return starts


def check_narration_scene_drift(
    scene_build_paths: list[Path],
    planned_durations: list[float],
    tolerance_ratio: float = 0.5,
) -> list[str]:
    """Mục 8, phần 5: so thời lượng THỰC TẾ từng đoạn đã dựng (đã ghép giọng
    đọc + video, xem production_pipeline._build_beat_scenes) với thời lượng
    DỰ KIẾN theo storyboard gốc (tổng độ dài các cửa sổ cảnh thuộc đoạn đó).
    Lệch quá `tolerance_ratio` là dấu hiệu giọng đọc đã bị cắt ngắn/kéo dài
    bất thường so với kế hoạch storyboard (kế thừa tinh thần skill
    narration-scene-alignment) — CHỈ CẢNH BÁO, không tự sửa gì.

    `scene_build_paths` và `planned_durations` PHẢI cùng độ dài và cùng thứ
    tự (1 đoạn <-> 1 giá trị dự kiến)."""
    warnings: list[str] = []
    for i, (path, planned) in enumerate(zip(scene_build_paths, planned_durations), start=1):
        if planned <= 0:
            continue
        actual = probe_video_stream(path).duration
        diff_ratio = abs(actual - planned) / planned
        if diff_ratio > tolerance_ratio:
            warnings.append(
                f"Đoạn {i} ({path.name}): thời lượng thực tế {actual:.1f}s lệch "
                f"{diff_ratio * 100:.0f}% so với dự kiến {planned:.1f}s theo storyboard "
                "— kiểm tra lại giọng đọc có bị cắt ngắn/dài bất thường không."
            )
    return warnings


def _normalize_ocr_text(text: str) -> str:
    return " ".join(text.upper().split())


def check_poster_text(
    poster_png_path: Path,
    expected_title: str,
    expected_subtitle: str = "",
    similarity_threshold: float = 0.6,
) -> list[str]:
    """Mục 8, phần 6: OCR ảnh poster đã dựng (drawtext, xem
    video_builder.generate_title_card_image), so khớp mờ với tiêu đề/phụ đề
    DỰ KIẾN — phát hiện chữ lem nhem/sai chính tả do lỗi render drawtext
    (thiếu ký tự trong font, escape sai...). Cần Tesseract-OCR (binary hệ
    thống, giống ffmpeg) — máy CHƯA CÀI thì trả về đúng 1 cảnh báo rõ ràng,
    KHÔNG ném lỗi (không chặn phần còn lại của Mục 8)."""
    if not _TESSERACT:
        return [
            "Chưa cài Tesseract-OCR trên máy này — bỏ qua kiểm tra chữ trên poster "
            "(cài đặt: https://github.com/tesseract-ocr/tesseract, rồi thử lại)."
        ]
    import pytesseract
    from PIL import Image

    pytesseract.pytesseract.tesseract_cmd = _TESSERACT
    recognized = _normalize_ocr_text(pytesseract.image_to_string(Image.open(poster_png_path)))

    warnings: list[str] = []
    for label, expected in (("tiêu đề", expected_title), ("phụ đề", expected_subtitle)):
        expected_norm = _normalize_ocr_text(expected)
        if not expected_norm:
            continue
        if expected_norm in recognized:
            continue
        ratio = difflib.SequenceMatcher(None, recognized, expected_norm).ratio()
        if ratio < similarity_threshold:
            warnings.append(
                f"Chữ {label} trên poster có thể bị lỗi hiển thị (không khớp văn bản "
                f"OCR đọc được, độ khớp {ratio:.2f}, kỳ vọng: '{expected}')."
            )
    return warnings
