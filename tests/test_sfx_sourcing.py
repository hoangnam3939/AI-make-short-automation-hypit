from pathlib import Path

from app.services.sfx_sourcing import (
    ScenePlan,
    SfxEntry,
    SfxLayer,
    apply_step13_sfx,
    build_sfx_index,
    find_best_sfx,
)
from app.services.video_builder import build_scene, generate_narration
import asyncio


def test_find_best_sfx_picks_highest_keyword_overlap():
    index = [
        SfxEntry(title="Tiếng trống trận chiến đấu", mp3_url="https://example.com/a.mp3"),
        SfxEntry(title="Tiếng vỗ tay khán giả", mp3_url="https://example.com/b.mp3"),
        SfxEntry(title="Tiếng ngựa phi nước đại", mp3_url="https://example.com/c.mp3"),
    ]
    best = find_best_sfx("đoàn quân cưỡi ngựa phi nhanh ra trận", index)
    assert best is not None
    assert best.mp3_url == "https://example.com/c.mp3"


def test_find_best_sfx_returns_none_when_no_overlap():
    index = [SfxEntry(title="Tiếng vỗ tay khán giả", mp3_url="https://example.com/b.mp3")]
    assert find_best_sfx("máy bay phản lực", index) is None


def test_build_sfx_index_real_network():
    """Test thật: tải 1 trang danh mục thật trên tiengdong.com, phải ra ít nhất vài chục hiệu ứng."""
    index = build_sfx_index(["https://tiengdong.com/danh-nhau-vu-khi"])
    assert len(index) >= 10
    assert all(e.mp3_url.endswith(".mp3") or ".mp3" in e.mp3_url for e in index)
    assert all(e.title for e in index)


def test_apply_step13_sfx_end_to_end_real(tmp_path):
    """Test thật đầu-cuối: dựng 1 video 2 cảnh placeholder, tải hiệu ứng thật từ
    tiengdong.com, hòa NHIỀU LỚP vào video cuối theo ĐÚNG TỪNG CẢNH (không phải
    theo cả đoạn lời dẫn — xem lỗi thật đã sửa 2026-09-13), kiểm tra file
    audio+video ra đúng."""
    audio1 = tmp_path / "audio" / "scene_01.mp3"
    audio2 = tmp_path / "audio" / "scene_02.mp3"
    asyncio.run(generate_narration("Cảnh một, tiếng trống trận vang lên.", "vi-VN", audio1))
    asyncio.run(generate_narration("Cảnh hai, đoàn quân xung trận.", "vi-VN", audio2))

    build_dir = tmp_path / "build"
    r1 = build_scene(audio1, build_dir / "scene_01.mp4", video_path=None, format_="long")
    r2 = build_scene(audio2, build_dir / "scene_02.mp4", video_path=None, format_="long")

    from app.services.video_builder import concat_scenes
    final = concat_scenes([r1.video_path, r2.video_path], tmp_path / "output" / "final.mp4")

    scene_plans = [
        ScenePlan(
            scene_n=1, start_sec=0.0, duration_sec=r1.duration_sec,
            layers=[SfxLayer(query_vi="tiếng trống trận đánh", gain_db=-6.0)],
        ),
        ScenePlan(
            scene_n=2, start_sec=r1.duration_sec, duration_sec=r2.duration_sec,
            layers=[
                SfxLayer(query_vi="tiếng ngựa phi nước đại", gain_db=-6.0),
                SfxLayer(query_vi="tiếng hò hét reo hò", gain_db=-12.0),
            ],
        ),
    ]

    out = apply_step13_sfx(
        final,
        scene_plans=scene_plans,
        out_path=tmp_path / "output" / "final_with_sfx.mp4",
        workdir=tmp_path / "sfx",
    )
    assert out.exists()
    assert out.stat().st_size > 0
