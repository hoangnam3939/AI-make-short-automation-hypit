"""Bước 3 (README) — khi người dùng chọn từ 2 ngôn ngữ giọng đọc trở lên, cho phép
chọn giữa 2 chế độ xuất video:
  - "sequential": xuất từng ngôn ngữ một, dừng lại hỏi người dùng sau mỗi ngôn ngữ
    trước khi sang ngôn ngữ tiếp theo (dùng callback `on_language_done`).
  - "batch": xuất tất cả ngôn ngữ cùng lúc (chạy song song bằng asyncio.gather).

Tái dùng đúng hàm dựng cảnh/giọng đọc thật đã có ở video_builder.py (Bước 10).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.services.video_builder import build_scene, concat_scenes, generate_narration


@dataclass
class LanguageExportResult:
    language_code: str
    final_video_path: Path


async def export_one_language(
    language_code: str,
    beats_text: list[str],
    scene_video_paths: list[Path | None],
    workdir: Path,
    format_: str = "long",
) -> LanguageExportResult:
    """Dựng trọn 1 video hoàn chỉnh cho 1 ngôn ngữ: sinh giọng đọc từng cảnh
    (đúng văn bản của ngôn ngữ đó) -> dựng từng cảnh -> ghép lại thành 1 file."""
    if len(beats_text) != len(scene_video_paths):
        raise ValueError(
            f"Số đoạn lời dẫn ({len(beats_text)}) phải khớp số cảnh video ({len(scene_video_paths)})."
        )

    lang_dir = workdir / language_code
    scene_outputs: list[Path] = []
    for i, (text, clip) in enumerate(zip(beats_text, scene_video_paths), start=1):
        audio_path = lang_dir / "audio" / f"scene_{i:02d}.mp3"
        await generate_narration(text, language_code, audio_path)
        scene_out = lang_dir / "build" / f"scene_{i:02d}.mp4"
        build_scene(audio_path, scene_out, video_path=clip, format_=format_)
        scene_outputs.append(scene_out)

    final = concat_scenes(scene_outputs, lang_dir / "final.mp4")
    return LanguageExportResult(language_code=language_code, final_video_path=final)


async def export_multi_language(
    language_codes: list[str],
    beats_text_by_lang: dict[str, list[str]],
    scene_video_paths: list[Path | None],
    workdir: Path,
    mode: str = "batch",
    format_: str = "long",
    on_language_done: Callable[[LanguageExportResult], None] | None = None,
) -> list[LanguageExportResult]:
    for lang in language_codes:
        if lang not in beats_text_by_lang:
            raise ValueError(f"Thiếu văn bản lời dẫn cho ngôn ngữ '{lang}'.")

    if mode == "batch":
        tasks = [
            export_one_language(lang, beats_text_by_lang[lang], scene_video_paths, workdir, format_)
            for lang in language_codes
        ]
        results = list(await asyncio.gather(*tasks))
        if on_language_done:
            for r in results:
                on_language_done(r)
        return results

    if mode == "sequential":
        results: list[LanguageExportResult] = []
        for lang in language_codes:
            r = await export_one_language(lang, beats_text_by_lang[lang], scene_video_paths, workdir, format_)
            results.append(r)
            if on_language_done:
                on_language_done(r)
        return results

    raise ValueError(f"mode phải là 'batch' hoặc 'sequential', nhận '{mode}'.")
