import asyncio

import pytest

from app.services.multilang_export import export_multi_language, export_one_language


def test_export_one_language_real(tmp_path):
    beats = ["Cảnh một, kiểm tra hệ thống.", "Cảnh hai, kiểm tra hệ thống."]
    result = asyncio.run(
        export_one_language("vi-VN", beats, [None, None], tmp_path)
    )
    assert result.language_code == "vi-VN"
    assert result.final_video_path.exists()
    assert result.final_video_path.stat().st_size > 0


def test_export_multi_language_batch_mode_real(tmp_path):
    beats_by_lang = {
        "vi-VN": ["Cảnh một tiếng Việt.", "Cảnh hai tiếng Việt."],
        "en-US": ["Scene one in English.", "Scene two in English."],
    }
    results = asyncio.run(
        export_multi_language(
            ["vi-VN", "en-US"], beats_by_lang, [None, None], tmp_path, mode="batch"
        )
    )
    assert {r.language_code for r in results} == {"vi-VN", "en-US"}
    for r in results:
        assert r.final_video_path.exists() and r.final_video_path.stat().st_size > 0


def test_export_multi_language_sequential_mode_calls_callback_in_order(tmp_path):
    beats_by_lang = {
        "vi-VN": ["Một.", "Hai."],
        "en-US": ["One.", "Two."],
    }
    order = []
    results = asyncio.run(
        export_multi_language(
            ["vi-VN", "en-US"], beats_by_lang, [None, None], tmp_path,
            mode="sequential", on_language_done=lambda r: order.append(r.language_code),
        )
    )
    assert order == ["vi-VN", "en-US"]
    assert [r.language_code for r in results] == ["vi-VN", "en-US"]


def test_export_multi_language_rejects_missing_text(tmp_path):
    with pytest.raises(ValueError):
        asyncio.run(
            export_multi_language(
                ["vi-VN", "en-US"], {"vi-VN": ["Một."]}, [None], tmp_path, mode="batch"
            )
        )


def test_export_multi_language_rejects_bad_mode(tmp_path):
    beats_by_lang = {"vi-VN": ["Một."]}
    with pytest.raises(ValueError):
        asyncio.run(
            export_multi_language(["vi-VN"], beats_by_lang, [None], tmp_path, mode="weird")
        )
