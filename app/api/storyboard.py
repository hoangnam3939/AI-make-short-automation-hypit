"""Bước 6-7 (Mục 3, V3) qua API — chia cảnh theo pacing ~8s/cảnh (thuần logic,
không cần AI key) rồi sinh prompt AI cho từng cảnh (cần AI key)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.character_bible import ABSOLUTE_MAX_CHARACTERS, Character, CharacterBible
from app.services.llm import LlmCliError, LlmJsonParseError, LlmNotConfiguredError, LlmRefusalError
from app.services.storyboard import (
    DEFAULT_SCENE_SECONDS,
    ScriptBeat,
    SceneWindow,
    build_scene_windows,
    generate_scene_prompts,
    parse_script_beats,
)

router = APIRouter()


class BeatsInput(BaseModel):
    script_text: str = Field(..., min_length=1)


@router.post("/storyboard/beats")
def get_beats(payload: BeatsInput):
    beats = parse_script_beats(payload.script_text)
    if not beats:
        raise HTTPException(
            400,
            "Không tìm thấy timestamp dạng [MM:SS-MM:SS] trong kịch bản. "
            "Kịch bản cần chia timestamp trước khi lên storyboard.",
        )
    return {"beats": [{"start_sec": b.start_sec, "end_sec": b.end_sec, "text": b.text} for b in beats]}


class BeatIn(BaseModel):
    start_sec: int
    end_sec: int
    text: str


class ScenesInput(BaseModel):
    beats: list[BeatIn]
    scene_seconds: int = DEFAULT_SCENE_SECONDS


@router.post("/storyboard/scenes")
def get_scenes(payload: ScenesInput):
    beats = [ScriptBeat(start_sec=b.start_sec, end_sec=b.end_sec, text=b.text) for b in payload.beats]
    windows = build_scene_windows(beats, scene_seconds=payload.scene_seconds)
    return {
        "scenes": [
            {"scene_n": w.scene_n, "start_sec": w.start_sec, "end_sec": w.end_sec, "source_text": w.source_text}
            for w in windows
        ]
    }


class SceneWindowIn(BaseModel):
    scene_n: int
    start_sec: int
    end_sec: int
    source_text: str


class CharacterIn(BaseModel):
    name: str
    description: str


class PromptsInput(BaseModel):
    scenes: list[SceneWindowIn]
    characters: list[CharacterIn] = []
    style_hint: str = "cinematic, photorealistic"


@router.post("/storyboard/prompts")
def get_scene_prompts(payload: PromptsInput):
    bible = CharacterBible(max_characters=ABSOLUTE_MAX_CHARACTERS)
    for c in payload.characters:
        bible.add(Character(name=c.name, description=c.description))
    windows = [
        SceneWindow(scene_n=s.scene_n, start_sec=s.start_sec, end_sec=s.end_sec, source_text=s.source_text)
        for s in payload.scenes
    ]
    try:
        prompts = generate_scene_prompts(windows, bible, style_hint=payload.style_hint)
    except LlmNotConfiguredError as e:
        raise HTTPException(400, str(e))
    except LlmRefusalError as e:
        raise HTTPException(422, str(e))
    except LlmCliError as e:
        raise HTTPException(503, str(e))
    except LlmJsonParseError as e:
        raise HTTPException(502, str(e))
    except RuntimeError as e:
        # Lỗi nội dung cụ thể (VD "Claude trả về prompt RỖNG cho cảnh N") —
        # không phải lỗi cấu hình/từ chối/CLI, nhưng vẫn phải báo rõ ràng cho
        # người dùng (lỗi thật đã gặp 2026-09-15: trước đây bị nuốt im lặng,
        # khiến cả 37 cảnh trả về prompt rỗng không 1 lời cảnh báo — xem
        # storyboard.generate_scene_prompts()), thay vì để lọt thành lỗi 500
        # chung chung không rõ nguyên nhân.
        raise HTTPException(502, str(e))
    # Mục 8 (character_consistency.py) cần lại văn bản kịch bản gốc của mỗi
    # cảnh (để dò nhân vật nào xuất hiện) khi tới lúc /production/start —
    # echo lại nguyên `source_text` người dùng đã gửi lên, không cần Claude
    # sinh thêm gì.
    source_text_by_scene_n = {w.scene_n: w.source_text for w in windows}
    return {
        "prompts": [
            {
                "scene_n": p.scene_n, "start_sec": p.start_sec, "end_sec": p.end_sec, "prompt": p.prompt,
                "prompt_vi": p.prompt_vi, "scene_type": p.scene_type, "chart_data": p.chart_data,
                "source_text": source_text_by_scene_n.get(p.scene_n, ""),
            }
            for p in prompts
        ]
    }
