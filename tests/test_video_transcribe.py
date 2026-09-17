"""Test app/services/video_transcribe.py ("cái tai" — tách giọng nói
thành chữ). yt-dlp/faster-whisper là dependency ngoài + tải model nặng,
nên mock qua sys.modules (2 thư viện import LAZY bên trong hàm, không ở
đầu file) thay vì gọi thật — đúng tinh thần dự án chỉ mock phần cần
mạng/model nặng."""
import sys
import types

import pytest

from app.services import video_transcribe


def test_download_audio_raises_when_yt_dlp_missing(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "yt_dlp", None)
    with pytest.raises(video_transcribe.TranscribeNotConfiguredError, match="yt-dlp"):
        video_transcribe.download_audio("https://tiktok.com/@x/video/1", tmp_path)


def test_download_audio_raises_when_ffmpeg_missing(monkeypatch, tmp_path):
    fake_yt_dlp = types.ModuleType("yt_dlp")
    fake_yt_dlp.YoutubeDL = object  # não cần dùng tới nếu ffmpeg check chặn trước
    fake_yt_dlp.utils = types.SimpleNamespace(DownloadError=RuntimeError)
    monkeypatch.setitem(sys.modules, "yt_dlp", fake_yt_dlp)
    monkeypatch.setattr(video_transcribe.shutil, "which", lambda name: None)

    with pytest.raises(video_transcribe.TranscribeNotConfiguredError, match="ffmpeg"):
        video_transcribe.download_audio("https://tiktok.com/@x/video/1", tmp_path)


def _install_fake_yt_dlp(monkeypatch, *, download_error=None, write_file=True):
    class FakeDownloadError(RuntimeError):
        pass

    class FakeYoutubeDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

        def download(self, urls):
            if download_error is not None:
                raise download_error
            if write_file:
                out_dir = _outdir_from_template(self.opts["outtmpl"])
                (out_dir / "audio.wav").write_bytes(b"fake-wav-bytes")

    def _outdir_from_template(template: str):
        from pathlib import Path
        return Path(template).parent

    fake_module = types.ModuleType("yt_dlp")
    fake_module.YoutubeDL = FakeYoutubeDL
    fake_module.utils = types.SimpleNamespace(DownloadError=FakeDownloadError)
    monkeypatch.setitem(sys.modules, "yt_dlp", fake_module)
    monkeypatch.setattr(video_transcribe.shutil, "which", lambda name: "/usr/bin/ffmpeg")
    return fake_module


def test_download_audio_success(monkeypatch, tmp_path):
    _install_fake_yt_dlp(monkeypatch)
    result = video_transcribe.download_audio("https://youtube.com/watch?v=x", tmp_path)
    assert result == tmp_path / "audio.wav"
    assert result.exists()


def test_download_audio_wraps_download_error(monkeypatch, tmp_path):
    fake_module = _install_fake_yt_dlp(monkeypatch, download_error=None)
    fake_module.utils.DownloadError("dummy")  # sanity: class instantiates fine

    def download_raises(self, urls):
        raise fake_module.utils.DownloadError("video riêng tư")

    fake_module.YoutubeDL.download = download_raises

    with pytest.raises(ValueError, match="Không tải được"):
        video_transcribe.download_audio("https://tiktok.com/@x/video/2", tmp_path)


def test_download_audio_raises_if_no_audio_produced(monkeypatch, tmp_path):
    _install_fake_yt_dlp(monkeypatch, write_file=False)
    with pytest.raises(ValueError, match="không có tiếng"):
        video_transcribe.download_audio("https://youtube.com/watch?v=silent", tmp_path)


def _fake_segment(start, end, text):
    return types.SimpleNamespace(start=start, end=end, text=text)


def _install_fake_faster_whisper(monkeypatch, segments, language="vi", constructor_calls=None):
    detected_language = language

    class FakeWhisperModel:
        def __init__(self, model_size, device="cpu", compute_type="int8"):
            if constructor_calls is not None:
                constructor_calls.append(model_size)
            self.model_size = model_size

        def transcribe(self, audio_path, language=None):
            # Tham số `language` ở đây là ngôn ngữ NGƯỜI GỌI chỉ định trước (None =
            # tự nhận diện) — khác `detected_language` (ngôn ngữ model NHẬN RA sau khi
            # nghe audio), y hệt info.language thật của faster-whisper.
            info = types.SimpleNamespace(language=detected_language)
            return iter(segments), info

    fake_module = types.ModuleType("faster_whisper")
    fake_module.WhisperModel = FakeWhisperModel
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)
    video_transcribe._model_cache.clear()
    return fake_module


def test_transcribe_audio_raises_when_faster_whisper_missing(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "faster_whisper", None)
    video_transcribe._model_cache.clear()
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"fake")
    with pytest.raises(video_transcribe.TranscribeNotConfiguredError, match="faster-whisper"):
        video_transcribe.transcribe_audio(audio_path)


def test_transcribe_audio_joins_segments(monkeypatch, tmp_path):
    segments = [_fake_segment(0.0, 1.5, "Xin chào"), _fake_segment(1.5, 3.0, "các bạn.")]
    _install_fake_faster_whisper(monkeypatch, segments, language="vi")
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"fake")

    result = video_transcribe.transcribe_audio(audio_path, model_size="small")

    assert result.text == "Xin chào các bạn."
    assert result.language == "vi"
    assert len(result.segments) == 2
    assert result.segments[0].start == 0.0


def test_transcribe_audio_raises_when_no_speech_detected(monkeypatch, tmp_path):
    _install_fake_faster_whisper(monkeypatch, [])
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"fake")
    with pytest.raises(ValueError, match="Không nhận ra lời nói"):
        video_transcribe.transcribe_audio(audio_path)


def test_transcribe_audio_caches_model_by_size(monkeypatch, tmp_path):
    constructor_calls = []
    _install_fake_faster_whisper(
        monkeypatch, [_fake_segment(0, 1, "chào")], constructor_calls=constructor_calls,
    )
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"fake")

    video_transcribe.transcribe_audio(audio_path, model_size="small")
    video_transcribe.transcribe_audio(audio_path, model_size="small")

    assert constructor_calls == ["small"]


def test_transcribe_video_url_downloads_then_transcribes(monkeypatch, tmp_path):
    calls = {}

    def fake_download_audio(url, out_dir):
        calls["url"] = url
        calls["out_dir"] = out_dir
        path = out_dir / "audio.wav"
        path.write_bytes(b"fake")
        return path

    def fake_transcribe_audio(audio_path, model_size=video_transcribe.DEFAULT_MODEL_SIZE):
        calls["model_size"] = model_size
        return video_transcribe.TranscriptResult(text="nội dung video", language="vi")

    monkeypatch.setattr(video_transcribe, "download_audio", fake_download_audio)
    monkeypatch.setattr(video_transcribe, "transcribe_audio", fake_transcribe_audio)

    result = video_transcribe.transcribe_video_url("https://tiktok.com/@x/video/3", model_size="base")

    assert result.text == "nội dung video"
    assert calls["url"] == "https://tiktok.com/@x/video/3"
    assert calls["model_size"] == "base"
    # Thư mục tạm phải được dọn sạch sau khi hàm chạy xong.
    assert not calls["out_dir"].exists()
