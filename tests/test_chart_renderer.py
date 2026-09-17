"""Test chart_renderer.py (Bước 8, loại hình "biểu đồ") — chạy matplotlib
THẬT (nhẹ, không cần AI/ffmpeg), chỉ kiểm tra ra đúng file PNG hợp lệ."""
from app.services.chart_renderer import render_chart_png


def test_render_chart_png_bar_creates_nonempty_file(tmp_path):
    chart_data = {"chart_type": "bar", "labels": ["Ta", "Địch"], "values": [5, 20]}
    out = tmp_path / "chart.png"
    result = render_chart_png(chart_data, "So sánh quân số", out)
    assert result == out
    assert out.exists()
    assert out.stat().st_size > 0


def test_render_chart_png_line_and_pie_also_work(tmp_path):
    for chart_type in ("line", "pie"):
        chart_data = {"chart_type": chart_type, "labels": ["A", "B", "C"], "values": [1, 2, 3]}
        out = tmp_path / f"chart_{chart_type}.png"
        render_chart_png(chart_data, "Caption", out)
        assert out.exists() and out.stat().st_size > 0


def test_render_chart_png_falls_back_to_bar_on_unknown_type(tmp_path):
    chart_data = {"chart_type": "khong-hop-le", "labels": ["A"], "values": [1]}
    out = tmp_path / "chart.png"
    render_chart_png(chart_data, "Caption", out)
    assert out.exists()


def test_render_chart_png_handles_missing_data_without_raising(tmp_path):
    out = tmp_path / "empty_chart.png"
    result = render_chart_png({}, "Chưa có dữ liệu", out)
    assert result.exists()
    assert result.stat().st_size > 0


def test_render_chart_png_short_format_uses_portrait_figsize(tmp_path):
    out = tmp_path / "chart_short.png"
    render_chart_png({"labels": ["A"], "values": [1]}, "Caption", out, format_="short")
    assert out.exists()
