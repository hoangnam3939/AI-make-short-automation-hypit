"""Bước 8 (Mục 3, V3): "App tự quyết cảnh nào cần video AI, cảnh nào dùng
ảnh tĩnh, cảnh nào dùng b-roll, cảnh nào cần chữ động, cảnh nào cần biểu đồ."
Loại hình do storyboard.generate_scene_prompts() quyết định (field
`scene_type` trên ScenePrompt, xem SCENE_TYPES) — module này chỉ lo phần
DỰNG THẬT cho từng loại.

HỢP ĐỒNG chung (bắt buộc mọi renderer tuân theo): nhận prompt/chart_data +
duration_sec + format_ + workdir, LUÔN trả về 1 Path video (libx264 + audio
câm chuẩn hoá, đúng tỷ lệ format_) — GIỐNG HỆT những gì
flow.generate_video_with_retry() vốn trả về. Nhờ vậy toàn bộ phần sau
(_build_beat_clips, _apply_sfx, ghép đa ngôn ngữ...) trong
production_pipeline.py không cần biết/sửa gì khi thêm loại hình mới —
đúng nguyên tắc "cảnh hình ảnh KHÔNG phụ thuộc ngôn ngữ, tạo 1 lần dùng
chung" đã có từ trước.

LƯU Ý (v1 — giới hạn đã biết): motion_text/chart hiện luôn hiển thị chữ/
nhãn TIẾNG ANH (đúng quy ước prompt AI Bước 7) để dùng chung được cho mọi
ngôn ngữ xuất video, giống ai_video/static_image/b_roll. Nếu sau này cần
chữ đúng theo từng ngôn ngữ video, 2 loại này sẽ phải tách ra dựng RIÊNG
cho từng ngôn ngữ thay vì dùng chung như hiện tại — chưa làm ở bản này.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from app.services import google_flow_driver as flow
from app.services.chart_renderer import render_chart_png
from app.services.video_builder import FFMPEG, generate_title_card_image, image_to_title_clip


def _probe_duration(path: Path) -> float:
    # Import trễ (không phải ở top-level) để tránh phụ thuộc vòng
    # error_checker.py <-> scene_renderers.py trong tương lai nếu Mục 8 cần
    # gọi ngược lại renderer nào đó.
    from app.services.error_checker import probe_video_stream

    return probe_video_stream(path).duration


def _extract_representative_frame(video_path: Path, out_png: Path) -> Path:
    """Trích 1 khung hình ở GIỮA video ra PNG — dùng làm ảnh giữ đứng hình
    cho static_image, giữ đúng nhân vật/bối cảnh Flow đã vẽ ra."""
    duration = _probe_duration(video_path)
    mid = max(0.0, duration / 2)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [FFMPEG, "-y", "-ss", f"{mid:.2f}", "-i", str(video_path), "-frames:v", "1", str(out_png)],
        check=True, capture_output=True,
    )
    return out_png


def render_ai_video(prompt: str, duration_sec: float, format_: str, workdir: Path, chart_data: dict | None = None) -> Path:
    """ai_video: hành vi CŨ, không đổi — gọi thẳng Google Flow. `workdir`
    ở đây LÀ thư mục tải riêng của đúng cảnh này (do
    production_pipeline._generate_scenes() truyền vào), không phải thư mục
    job dùng chung."""
    return flow.generate_video_with_retry(prompt, workdir)


def render_b_roll(prompt: str, duration_sec: float, format_: str, workdir: Path, chart_data: dict | None = None) -> Path:
    """b_roll: CŨNG gọi Flow — khác biệt duy nhất (bỏ chèn mô tả nhân vật)
    đã xử lý ở storyboard.py lúc build prompt, không phải ở đây."""
    return flow.generate_video_with_retry(prompt, workdir)


def render_static_image(prompt: str, duration_sec: float, format_: str, workdir: Path, chart_data: dict | None = None) -> Path:
    """static_image: gọi Flow để LẤY ĐÚNG hình ảnh nhân vật/bối cảnh (giữ
    đồng nhất nhân vật, Mục 5), rồi trích 1 khung hình và giữ đứng hình đủ
    duration_sec — rẻ hơn cả đoạn video AI, vẫn giữ đúng hình ảnh nhân vật."""
    clip_path = flow.generate_video_with_retry(prompt, workdir)
    frame_png = workdir / "static_frame.png"
    _extract_representative_frame(clip_path, frame_png)
    return image_to_title_clip(frame_png, workdir / "static_image_clip.mp4", duration_sec=duration_sec, format_=format_)


def render_motion_text_clip(prompt: str, duration_sec: float, format_: str, workdir: Path, chart_data: dict | None = None) -> Path:
    """motion_text: THUẦN ffmpeg, KHÔNG gọi Flow. `prompt` ở đây chính là
    đoạn chữ/từ khoá cần hiển thị lớn (xem system prompt của
    storyboard.generate_scene_prompts). Tái dùng đúng cách vẽ chữ an toàn
    dấu tiếng Việt của generate_title_card_image (textfile=, không phải
    text=, xem docstring hàm đó)."""
    frame_png = workdir / "motion_text_frame.png"
    generate_title_card_image(prompt, frame_png, format_=format_)
    return image_to_title_clip(frame_png, workdir / "motion_text_clip.mp4", duration_sec=duration_sec, format_=format_)


def render_chart_clip(prompt: str, duration_sec: float, format_: str, workdir: Path, chart_data: dict | None = None) -> Path:
    """chart: THUẦN Python (matplotlib) + ffmpeg, KHÔNG gọi Flow. Vẽ biểu đồ
    từ `chart_data` (xem chart_renderer.py), lấy `prompt` làm tiêu đề biểu
    đồ, rồi giữ đứng hình như static_image."""
    chart_png = workdir / "chart.png"
    render_chart_png(chart_data or {}, prompt, chart_png, format_=format_)
    return image_to_title_clip(chart_png, workdir / "chart_clip.mp4", duration_sec=duration_sec, format_=format_)


RENDERERS = {
    "ai_video": render_ai_video,
    "b_roll": render_b_roll,
    "static_image": render_static_image,
    "motion_text": render_motion_text_clip,
    "chart": render_chart_clip,
}


def render_scene(scene_type: str, prompt: str, duration_sec: float, format_: str, workdir: Path, chart_data: dict | None = None) -> Path:
    """Dispatch theo scene_type — điểm gọi DUY NHẤT từ
    production_pipeline._generate_scenes(). scene_type lạ (không có trong
    RENDERERS) rơi về ai_video, không chặn cả cảnh."""
    renderer = RENDERERS.get(scene_type, RENDERERS["ai_video"])
    return renderer(prompt, duration_sec, format_, workdir, chart_data)
