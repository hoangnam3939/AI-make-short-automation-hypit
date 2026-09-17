"""Bước 8 (Mục 3, V3), loại hình "biểu đồ" — vẽ biểu đồ THẬT từ dữ liệu
Claude đề xuất trong storyboard.generate_scene_prompts() (field `chart_data`
trên ScenePrompt: {"chart_type": "bar"|"line"|"pie", "labels": [...],
"values": [...]}). Ra PNG, KHÔNG cần gọi AI/Flow — dùng chung matplotlib
(dependency mới, xem requirements.txt).

Tách riêng module này (không gộp vào scene_renderers.py) để test được PHẦN
VẼ BIỂU ĐỒ thuần tuý mà không cần ffmpeg — scene_renderers.py chỉ gọi
render_chart_png() rồi tự giữ đứng hình như static_image."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # không cần màn hình — chạy được trên server/CI
import matplotlib.pyplot as plt

CHART_TYPES = ("bar", "line", "pie")
DEFAULT_CHART_TYPE = "bar"

# Bảng màu trung tính, đủ tương phản trên nền poster tối đã dùng ở
# generate_title_card_image() — tránh trùng đúng 1 màu với nền/chữ trắng.
_PALETTE = ["#E8C468", "#5583CA", "#CF5F54", "#1D9F70", "#7458B8", "#EB7F8F"]


def render_chart_png(chart_data: dict, caption: str, out_path: Path, format_: str = "long") -> Path:
    """Vẽ 1 biểu đồ từ `chart_data` (thiếu labels/values -> vẽ khung trống
    kèm caption, KHÔNG ném lỗi — 1 cảnh lỗi không được chặn cả video, đúng
    tinh thần production_pipeline.py)."""
    chart_type = chart_data.get("chart_type") or DEFAULT_CHART_TYPE
    if chart_type not in CHART_TYPES:
        chart_type = DEFAULT_CHART_TYPE
    labels = [str(l) for l in chart_data.get("labels", [])]
    values = [float(v) for v in chart_data.get("values", [])] if chart_data.get("values") else []

    # Khổ ảnh khớp tỷ lệ video đích (16:9 dài / 9:16 short) để static_image/
    # chart không bị méo khi image_to_title_clip() scale+pad lại.
    figsize = (12.8, 7.2) if format_ == "long" else (7.2, 12.8)
    fig, ax = plt.subplots(figsize=figsize, facecolor="#0d0805")
    ax.set_facecolor("#0d0805")

    if labels and values and len(labels) == len(values):
        colors = [_PALETTE[i % len(_PALETTE)] for i in range(len(labels))]
        if chart_type == "bar":
            ax.bar(labels, values, color=colors)
        elif chart_type == "line":
            ax.plot(labels, values, color=_PALETTE[0], marker="o", linewidth=3)
        elif chart_type == "pie":
            ax.pie(values, labels=labels, colors=colors, textprops={"color": "white", "fontsize": 14})
        if chart_type != "pie":
            ax.tick_params(colors="white", labelsize=13)
            for spine in ax.spines.values():
                spine.set_color("#555555")
    else:
        ax.text(0.5, 0.5, "(chưa có dữ liệu biểu đồ)", color="white", ha="center", va="center", fontsize=18)
        ax.axis("off")

    ax.set_title(caption, color="white", fontsize=20, fontweight="bold", pad=20)
    fig.tight_layout()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, facecolor=fig.get_facecolor())
    plt.close(fig)
    return out_path
