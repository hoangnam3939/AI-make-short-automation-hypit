"""Ghép video thật — Bước 10, Nhiem_Vu_Goc_App_Video_AI_V3.docx.

Tái sử dụng ĐÚNG kiến trúc đã chứng minh qua 4 pipeline thật (Troy, Thánh Gióng,
Sơn Tinh Thủy Tinh, Salamis) — xem .claude/skills/run-video-pipeline/SKILL.md.
Không cần LLM, không cần API key AI — chỉ cần edge-tts (miễn phí) + ffmpeg.

Khác biệt so với 4 pipeline cũ: tham số hóa đầy đủ (project dir, tỷ lệ khung hình
16:9/9:16, ngôn ngữ) thay vì hardcode riêng từng dự án.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import edge_tts

# ffmpeg/ffprobe: tự dò trong PATH của máy đang chạy — đường dẫn cứng cũ
# (C:\Users\User\...) chỉ đúng trên máy phát triển gốc, gặp lỗi thật khi
# chạy trên máy khác (username khác, gói cài WinGet khác: "Essentials" thay
# vì "full_build"). shutil.which() trả về None nếu không tìm thấy — báo lỗi
# rõ ràng ngay lúc import thay vì lỗi khó hiểu lúc chạy ffmpeg.
FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")
if FFMPEG is None or FFPROBE is None:
    raise RuntimeError(
        "Không tìm thấy ffmpeg/ffprobe trong PATH của máy này. Cài ffmpeg "
        "(vd: winget install Gyan.FFmpeg.Essentials) rồi thử lại."
    )

# Giọng đọc edge-tts đã xác nhận THẬT tồn tại (truy vấn edge_tts.list_voices() 2026-09-11)
# cho đủ 20 ngôn ngữ — Mục 6, V3.
VOICE_MAP = {
    "en-US": "en-US-ChristopherNeural",  # giọng nam trầm, mạnh mẽ, quyết liệt — theo yêu cầu 2026-09-13
    "vi-VN": "vi-VN-NamMinhNeural",
    "zh-CN": "zh-CN-XiaoxiaoNeural",
    "es-ES": "es-ES-XimenaNeural",
    "ru-RU": "ru-RU-SvetlanaNeural",
    "ar-SA": "ar-SA-ZariyahNeural",
    "hi-IN": "hi-IN-SwaraNeural",
    "pt-BR": "pt-BR-ThalitaMultilingualNeural",
    "fr-FR": "fr-FR-VivienneMultilingualNeural",
    "ja-JP": "ja-JP-NanamiNeural",
    "tr-TR": "tr-TR-EmelNeural",
    "de-DE": "de-DE-SeraphinaMultilingualNeural",
    "ko-KR": "ko-KR-InJoonNeural",
    "id-ID": "id-ID-GadisNeural",
    "th-TH": "th-TH-PremwadeeNeural",
    "it-IT": "it-IT-DiegoNeural",
    "pl-PL": "pl-PL-ZofiaNeural",
    "bn-IN": "bn-IN-TanishaaNeural",
    "ur-PK": "ur-PK-UzmaNeural",
    "nl-NL": "nl-NL-ColetteNeural",
}

RESOLUTIONS = {
    "long": (1920, 1080),   # 16:9 — Muc 4, V3
    "short": (1080, 1920),  # 9:16 — Muc 4, V3
}
FPS = 24


@dataclass
class SceneBuildResult:
    scene_n: int
    audio_path: Path
    video_path: Path
    duration_sec: float
    had_real_clip: bool


async def generate_narration(text: str, language_code: str, out_path: Path, retries: int = 4) -> Path:
    """Sinh giọng đọc bằng edge-tts. Giữ đúng logic retry đã chứng minh ở
    pipeline/generate_tts.py (4 dự án cũ)."""
    if language_code not in VOICE_MAP:
        raise ValueError(f"Chưa có giọng đọc cho ngôn ngữ '{language_code}'. Xem VOICE_MAP.")
    voice = VOICE_MAP[language_code]
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.exists() and out_path.stat().st_size > 0:
        return out_path

    last_err = None
    for attempt in range(retries):
        try:
            communicate = edge_tts.Communicate(text, voice, rate="-4%")
            await communicate.save(str(out_path))
            return out_path
        except Exception as e:  # noqa: BLE001 - muốn bắt mọi lỗi mạng/edge-tts để retry
            last_err = e
            await asyncio.sleep(2)
    raise RuntimeError(f"Sinh giọng đọc thất bại sau {retries} lần thử: {last_err}")


def _probe_duration(path: Path) -> float:
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def build_scene(
    audio_path: Path,
    out_path: Path,
    video_path: Path | None,
    format_: str,  # "long" | "short"
) -> SceneBuildResult:
    """Dựng 1 cảnh: ghép clip AI (nếu có) hoặc placeholder tối màu (không chữ,
    theo đúng preference đã ghi nhận) với giọng đọc, canh đúng độ dài audio + 0.25s
    — HOẶC đúng độ dài video gốc nếu video dài hơn giọng đọc (xem lỗi thật bên dưới).

    Giữ NGUYÊN cấu trúc lệnh ffmpeg đã chứng minh ở 4 pipeline cũ.

    Lỗi thật đã sửa (2026-09-13, video Quang Trung): trước đây `target_dur`
    CHỈ tính theo độ dài giọng đọc, khiến khi giọng đọc 1 đoạn ngắn hơn tổng
    độ dài các cảnh Flow đã tạo cho đoạn đó, phần video thừa bị CẮT MẤT HẲN
    (mất cả cảnh, dù đã tốn phí tạo qua Google Flow) — xem
    `.claude/skills/narration-scene-alignment/SKILL.md`. Sửa: lấy
    `target_dur` = giá trị LỚN HƠN giữa (độ dài giọng đọc + 0.25s) và độ dài
    video gốc — giọng đọc ngắn hơn thì phần video còn lại vẫn hiện đủ,
    chỉ không có giọng đọc đè lên (`apad` tự lấp bằng im lặng), đúng tinh
    thần "cảnh nào không có lời dẫn thì chỉ cần hiệu ứng nền cũng được"."""
    width, height = RESOLUTIONS[format_]
    audio_dur = _probe_duration(audio_path)
    video_dur = _probe_duration(video_path) if (video_path is not None and video_path.exists()) else 0.0
    target_dur = round(max(audio_dur + 0.25, video_dur), 3)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    vf = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={FPS}"
    has_video = video_path is not None and video_path.exists()

    if has_video:
        cmd = [
            FFMPEG, "-y",
            "-stream_loop", "-1", "-i", str(video_path),
            "-i", str(audio_path),
            "-t", str(target_dur),
            "-vf", vf,
            "-af", "apad",
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
            "-shortest",
            str(out_path),
        ]
    else:
        # Placeholder tối màu, KHÔNG chữ trên màn hình (feedback đã ghi nhận: user
        # không muốn text overlay ngay cả trên filler content).
        lavfi = f"color=c=0x120d0a:s={width}x{height}:d={target_dur}:r={FPS},noise=alls=8:allf=t+u,vignette=PI/4"
        cmd = [
            FFMPEG, "-y",
            "-f", "lavfi", "-i", lavfi,
            "-i", str(audio_path),
            "-af", "apad",
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
            "-t", str(target_dur),
            str(out_path),
        ]

    subprocess.run(cmd, check=True, capture_output=True)
    return SceneBuildResult(
        scene_n=0, audio_path=audio_path, video_path=out_path,
        duration_sec=target_dur, had_real_clip=has_video,
    )


def concat_scenes(scene_video_paths: list[Path], out_path: Path) -> Path:
    """Ghép danh sách cảnh đã dựng thành 1 video hoàn chỉnh — dùng ffmpeg concat demuxer,
    đúng kỹ thuật đã chứng minh (đường dẫn trong list ghi tương đối theo thư mục chứa
    concat_list.txt, tránh đúng lỗi đường dẫn đã gặp lúc build driver.sh)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    list_path = out_path.parent / "concat_list.txt"
    with open(list_path, "w", encoding="utf-8") as f:
        for p in scene_video_paths:
            f.write(f"file '{os.path.relpath(p, list_path.parent).replace(os.sep, '/')}'\n")

    cmd = [
        FFMPEG, "-y",
        "-f", "concat", "-safe", "0", "-i", str(list_path),
        "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        str(out_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path


def generate_title_card_image(
    title_text: str,
    out_path: Path,
    format_: str = "long",
    subtitle_text: str | None = None,
    background_image: Path | None = None,
) -> Path:
    """Poster/title card dựng THÀNH ẢNH TĨNH (PNG) bằng ffmpeg (drawtext), KHÔNG qua
    Veo3 — tránh đúng lỗi thật đã gặp: Veo3 tự vẽ chữ tiếng Việt lên hình hay sai dấu,
    phải sửa đi sửa lại rất mệt. Chữ ở đây do chính ffmpeg vẽ từ text file UTF-8 nên
    luôn đúng dấu 100%. `background_image`: nếu có (VD ảnh nền do Flow/Veo3 tạo riêng,
    không chữ), dùng làm nền thay vì màu nền trơn.

    Dùng textfile= (không dùng text=) để né hết lỗi escape ký tự đặc biệt (dấu ':',
    dấu '\'', ...) của bộ lọc drawtext khi truyền thẳng chuỗi tiếng Việt có dấu.
    """
    width, height = RESOLUTIONS[format_]
    workdir = out_path.parent
    workdir.mkdir(parents=True, exist_ok=True)

    # Lỗi thật gặp phải: đường dẫn tuyệt đối Windows (C:/Windows/Fonts/...) làm bộ
    # lọc drawtext của ffmpeg hiểu nhầm dấu ':' sau ổ đĩa là dấu phân cách option,
    # dù đã escape bằng dấu nháy đơn hay '\:' đều không ăn thua trên bản ffmpeg này.
    # Cách duy nhất chạy được thật: chạy ffmpeg với cwd=workdir, và chỉ dùng TÊN FILE
    # tương đối (không ổ đĩa, không dấu ':') cho mọi tham số fontfile=/textfile=.
    local_font = workdir / "arialbd_local.ttf"
    if not local_font.exists():
        shutil.copy("C:/Windows/Fonts/arialbd.ttf", local_font)

    title_file = workdir / f"{out_path.stem}_title.txt"
    title_file.write_text(title_text, encoding="utf-8")

    title_size = max(48, width // 16)
    filters = [
        f"drawtext=fontfile={local_font.name}:textfile={title_file.name}:"
        f"fontcolor=white:fontsize={title_size}:borderw=4:bordercolor=black@0.8:"
        f"x=(w-text_w)/2:y=(h-text_h)/2:line_spacing=12"
    ]

    if subtitle_text:
        subtitle_file = workdir / f"{out_path.stem}_subtitle.txt"
        subtitle_file.write_text(subtitle_text, encoding="utf-8")
        sub_size = max(28, width // 32)
        # Lỗi thật gặp phải: "(h-text_h)/2" trong drawtext của PHỤ ĐỀ chỉ tính theo
        # chiều cao CHỮ CỦA CHÍNH NÓ (1 dòng), không biết chiều cao thật của khối
        # TIÊU ĐỀ (nhiều dòng) — nên cộng lệch cố định title_size+40 là không đủ,
        # gây đè chữ khi tiêu đề có 2 dòng trở lên. Phải tự tính chiều cao khối
        # tiêu đề (số dòng x cỡ chữ x hệ số dãn dòng) rồi mới cộng khoảng cách.
        title_lines = title_text.count("\n") + 1
        title_block_height = title_lines * title_size * 1.3
        gap = title_block_height / 2 + 30
        filters.append(
            f"drawtext=fontfile={local_font.name}:textfile={subtitle_file.name}:"
            f"fontcolor=0xE8C468:fontsize={sub_size}:borderw=2:bordercolor=black@0.8:"
            f"x=(w-text_w)/2:y=(h-text_h)/2+{gap:.0f}"
        )

    vf = ",".join(filters)
    out_name = out_path.name

    if background_image is not None and background_image.exists():
        bg_local = workdir / f"_bg_{out_name}"
        if background_image.resolve() != bg_local.resolve():
            shutil.copy(background_image, bg_local)
        cmd = [
            FFMPEG, "-y",
            "-i", bg_local.name,
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}," + vf,
            "-frames:v", "1", "-update", "1",
            out_name,
        ]
    else:
        lavfi = f"color=c=0x0d0805:s={width}x{height}"
        cmd = [
            FFMPEG, "-y",
            "-f", "lavfi", "-i", lavfi,
            "-vf", vf,
            "-frames:v", "1", "-update", "1",
            out_name,
        ]
    subprocess.run(cmd, check=True, capture_output=True, cwd=str(workdir))
    return out_path


def image_to_title_clip(image_path: Path, out_path: Path, duration_sec: float, format_: str = "long") -> Path:
    """Biến 1 ảnh tĩnh (VD từ `generate_title_card_image`) thành 1 đoạn video
    câm dài `duration_sec` giây — dùng để ghép làm tiêu đề mở đầu (nối vào
    trước video chính bằng `concat_scenes`, xem `production_pipeline.py`).
    Có track audio câm lặng (cùng chuẩn với các cảnh khác: aac 44100Hz
    stereo) để concat demuxer -c copy không bị lỗi lệch định dạng audio
    giữa các đoạn nối lại."""
    width, height = RESOLUTIONS[format_]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        FFMPEG, "-y",
        "-loop", "1", "-i", str(image_path),
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-t", str(duration_sec),
        "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={FPS}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
        "-shortest",
        str(out_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path
