"""'Cái tai' của bếp (Mục 03 phiếu đánh giá danh-gia-kha-thi-short-automation.html):
tách giọng nói trong 1 video TikTok/YouTube thành chữ, để
app/services/video_source_import.py hiểu được video đó đang nói chuyện gì
TRƯỚC KHI giao cho LLM phân tích thành câu chuyện/công thức viral — khác
việc đọc 1 link bài báo (story_import.py), video không có sẵn chữ để đọc
thẳng.

2 bước:
1. Tải phần âm thanh của video (yt-dlp — hỗ trợ cả TikTok/YouTube/nhiều
   nền tảng khác với video công khai, không cần đăng nhập).
2. Nhận diện giọng nói -> chữ bằng faster-whisper (bản triển khai lại
   Whisper của OpenAI, chạy CPU chấp nhận được, không cần GPU) — CHẠY CỤC
   BỘ, miễn phí, không gửi audio ra dịch vụ ngoài nào.

Cả 2 thư viện (yt-dlp, faster-whisper) là dependency KHÔNG BẮT BUỘC cho
toàn app (chỉ agent này cần) — import trong hàm (không import ở đầu file)
để phần còn lại của app vẫn chạy được nếu máy chưa cài 2 package này."""
from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

# "small" là điểm cân bằng tốc độ/độ chính xác hợp lý trên CPU cho video
# ngắn (dưới vài phút) — đổi qua biến môi trường WHISPER_MODEL_SIZE nếu
# máy có GPU (dùng "medium"/"large-v3") hoặc muốn ưu tiên tốc độ ("tiny"/"base").
DEFAULT_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "small")

# Cache model đã tải theo kích cỡ — WhisperModel nạp xong tốn vài giây tới
# vài chục giây (tuỳ kích cỡ), không nên nạp lại mỗi lần gọi transcribe.
_model_cache: dict[str, object] = {}


class TranscribeNotConfiguredError(RuntimeError):
    """yt-dlp, ffmpeg, hoặc faster-whisper chưa được cài trên máy này."""


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass
class TranscriptResult:
    text: str
    language: str
    segments: list[TranscriptSegment] = field(default_factory=list)


def download_audio(url: str, out_dir: Path) -> Path:
    """Tải phần âm thanh của 1 video công khai (TikTok/YouTube/...) về
    `out_dir`, trả về đường dẫn file .wav. Cần yt-dlp (pip) + ffmpeg (đã là
    dependency BẮT BUỘC sẵn có của app, xem app/services/video_builder.py
    — dùng lại đúng binary đó, không cài thêm gì cho phần ffmpeg)."""
    try:
        import yt_dlp
    except ImportError as exc:
        raise TranscribeNotConfiguredError(
            "Chưa cài yt-dlp trên máy này. Chạy: pip install yt-dlp"
        ) from exc
    if shutil.which("ffmpeg") is None:
        raise TranscribeNotConfiguredError(
            "Chưa tìm thấy ffmpeg trong PATH của máy này — cần ffmpeg để tách "
            "âm thanh khỏi video (vd: winget install Gyan.FFmpeg.Essentials)."
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(out_dir / "audio.%(ext)s"),
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except yt_dlp.utils.DownloadError as exc:
        raise ValueError(
            f"Không tải được video/audio từ link này (link riêng tư, bị gỡ, hoặc "
            f"nền tảng chặn tải): {exc}"
        ) from exc

    audio_path = out_dir / "audio.wav"
    if not audio_path.exists():
        raise ValueError("Tải xong nhưng không thấy file âm thanh — video này có thể không có tiếng.")
    return audio_path


def _get_model(model_size: str):
    if model_size not in _model_cache:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise TranscribeNotConfiguredError(
                "Chưa cài faster-whisper trên máy này. Chạy: pip install faster-whisper"
            ) from exc
        _model_cache[model_size] = WhisperModel(model_size, device="cpu", compute_type="int8")
    return _model_cache[model_size]


def transcribe_audio(audio_path: Path, model_size: str = DEFAULT_MODEL_SIZE) -> TranscriptResult:
    """Nhận diện giọng nói trong file audio -> chữ, kèm mốc thời gian từng
    câu (dùng để phân tích nhịp/cấu trúc video ở video_source_import.py).
    Lần chạy đầu tiên với 1 model_size sẽ tự tải model faster-whisper
    (~150-500MB tuỳ kích cỡ) về máy — chỉ tải 1 lần, các lần sau dùng lại
    (xem _model_cache)."""
    model = _get_model(model_size)
    segments_iter, info = model.transcribe(str(audio_path), language=None)
    segments = [
        TranscriptSegment(start=s.start, end=s.end, text=s.text.strip())
        for s in segments_iter
    ]
    text = " ".join(s.text for s in segments if s.text).strip()
    if not text:
        raise ValueError("Không nhận ra lời nói nào trong video này (có thể video không có giọng nói).")
    return TranscriptResult(text=text, language=info.language, segments=segments)


def transcribe_video_url(url: str, model_size: str = DEFAULT_MODEL_SIZE) -> TranscriptResult:
    """Gộp cả 2 bước: tải audio từ 1 link video công khai rồi tách giọng
    nói thành chữ. Dùng thư mục tạm rồi dọn sạch ngay sau khi xong (kể cả
    khi lỗi giữa chừng) — không giữ lại file audio đã tải."""
    with tempfile.TemporaryDirectory(prefix="video_transcribe_") as tmp:
        audio_path = download_audio(url, Path(tmp))
        return transcribe_audio(audio_path, model_size=model_size)
