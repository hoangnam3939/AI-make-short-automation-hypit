"""Test scene_renderers.py (Bước 8 — 5 loại hình cảnh). motion_text/chart
chạy ffmpeg/matplotlib THẬT (không gọi Flow) — kiểm tra được đầu-cuối không
cần mock. static_image cần Flow (mock) để lấy 1 clip giả rồi trích khung
hình thật bằng ffmpeg. Dispatch (render_scene/RENDERERS) test bằng mock để
không tốn thời gian chạy renderer thật."""
import subprocess

from app.services import scene_renderers
from app.services.error_checker import probe_video_stream
from app.services.video_builder import FFMPEG


def _make_fake_flow_clip(path, duration=2.0):
    """Clip mp4 thật tối giản (màu + audio câm) đứng thay cho video Flow
    thật — chỉ cần đủ hợp lệ để ffprobe/ffmpeg trích khung hình được."""
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            FFMPEG, "-y",
            "-f", "lavfi", "-i", f"color=c=blue:s=640x360:d={duration}",
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t", str(duration), "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", str(path),
        ],
        check=True, capture_output=True,
    )
    return path


def test_render_motion_text_clip_creates_video_of_correct_duration(tmp_path):
    out = scene_renderers.render_motion_text_clip("BREAKING POINT", 3.0, "long", tmp_path)
    assert out.exists()
    info = probe_video_stream(out)
    assert abs(info.duration - 3.0) < 0.6
    assert (info.width, info.height) == (1920, 1080)


def test_render_motion_text_clip_short_format_is_vertical(tmp_path):
    out = scene_renderers.render_motion_text_clip("QUICK", 2.0, "short", tmp_path)
    info = probe_video_stream(out)
    assert info.height > info.width  # 9:16


def test_render_chart_clip_creates_video(tmp_path):
    chart_data = {"chart_type": "bar", "labels": ["Ta", "Địch"], "values": [5, 20]}
    out = scene_renderers.render_chart_clip("So sánh quân số", 2.5, "long", tmp_path, chart_data)
    assert out.exists()
    info = probe_video_stream(out)
    assert abs(info.duration - 2.5) < 0.6


def test_render_static_image_extracts_frame_from_flow_clip(monkeypatch, tmp_path):
    fake_clip = tmp_path / "flow_out" / "clip.mp4"

    def fake_generate_video_with_retry(prompt, output_dir, **kwargs):
        return _make_fake_flow_clip(output_dir / "clip.mp4")

    monkeypatch.setattr(scene_renderers.flow, "generate_video_with_retry", fake_generate_video_with_retry)

    out = scene_renderers.render_static_image("a warrior standing still", 2.0, "long", tmp_path)
    assert out.exists()
    info = probe_video_stream(out)
    assert abs(info.duration - 2.0) < 0.6


def test_render_ai_video_and_b_roll_both_delegate_to_flow(monkeypatch, tmp_path):
    calls = []

    def fake_generate_video_with_retry(prompt, output_dir, **kwargs):
        calls.append((prompt, output_dir))
        return output_dir / "clip.mp4"

    monkeypatch.setattr(scene_renderers.flow, "generate_video_with_retry", fake_generate_video_with_retry)

    scene_renderers.render_ai_video("prompt A", 8.0, "long", tmp_path / "s1")
    scene_renderers.render_b_roll("prompt B", 8.0, "long", tmp_path / "s2")
    assert len(calls) == 2
    assert calls[0][0] == "prompt A"
    assert calls[1][0] == "prompt B"


def test_render_scene_dispatches_by_scene_type(monkeypatch):
    from pathlib import Path

    called = {}

    def make_stub(name):
        def stub(prompt, duration_sec, format_, workdir, chart_data=None):
            called["name"] = name
            return workdir / "stub.mp4"
        return stub

    for scene_type in list(scene_renderers.RENDERERS):
        monkeypatch.setitem(scene_renderers.RENDERERS, scene_type, make_stub(scene_type))

    for scene_type in ["ai_video", "static_image", "b_roll", "motion_text", "chart"]:
        called.clear()
        scene_renderers.render_scene(scene_type, "prompt", 8.0, "long", Path("/tmp/x"))
        assert called["name"] == scene_type


def test_render_scene_falls_back_to_ai_video_for_unknown_type(monkeypatch):
    from pathlib import Path

    calls = []
    monkeypatch.setitem(
        scene_renderers.RENDERERS, "ai_video",
        lambda prompt, duration_sec, format_, workdir, chart_data=None: calls.append(1) or workdir,
    )
    scene_renderers.render_scene("khong-hop-le", "prompt", 8.0, "long", Path("/tmp/x"))
    assert calls == [1]
