"""Sổ Tay Nhân Vật (Mục 5, V3) qua API — stateless: frontend giữ danh sách
nhân vật, backend chỉ validate (giới hạn 10-20, trùng tên) và thực hiện
chèn mô tả nhân vật vào prompt cảnh."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import script_writer
from app.services.character_bible import (
    ABSOLUTE_MAX_CHARACTERS,
    DEFAULT_MAX_CHARACTERS,
    Character,
    CharacterBible,
    inject_character_descriptions,
)
from app.services.llm import LlmCliError, LlmNotConfiguredError, LlmRefusalError

router = APIRouter()


class CharacterIn(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)


class ValidateBibleInput(BaseModel):
    characters: list[CharacterIn]
    max_characters: int = 10


@router.post("/characters/validate")
def validate_bible(payload: ValidateBibleInput):
    if payload.max_characters > ABSOLUTE_MAX_CHARACTERS:
        raise HTTPException(400, f"max_characters không được vượt quá {ABSOLUTE_MAX_CHARACTERS}")

    bible = CharacterBible(max_characters=payload.max_characters)
    for c in payload.characters:
        try:
            bible.add(Character(name=c.name, description=c.description))
        except ValueError as e:
            raise HTTPException(400, str(e))
    return {"valid": True, "count": len(bible.characters)}


class SuggestCharactersInput(BaseModel):
    story: str = Field(..., min_length=1)
    max_characters: int = DEFAULT_MAX_CHARACTERS


@router.post("/characters/suggest")
def suggest_characters(payload: SuggestCharactersInput):
    """Bước 1: gợi ý danh sách nhân vật từ câu chuyện đã viết (Bước 2) —
    CHỈ trả gợi ý để người dùng xem/sửa trên giao diện, không tự ghi vào
    dự án (xem script_writer.suggest_characters)."""
    if payload.max_characters > ABSOLUTE_MAX_CHARACTERS:
        raise HTTPException(400, f"max_characters không được vượt quá {ABSOLUTE_MAX_CHARACTERS}")
    try:
        characters = script_writer.suggest_characters(payload.story, max_characters=payload.max_characters)
    except LlmNotConfiguredError as e:
        raise HTTPException(400, str(e))
    except LlmRefusalError as e:
        raise HTTPException(422, str(e))
    except LlmCliError as e:
        raise HTTPException(503, str(e))
    return {"characters": characters}


class InjectInput(BaseModel):
    scene_prompt: str = Field(..., min_length=1)
    scene_text: str = Field(..., min_length=1)
    characters: list[CharacterIn]


@router.post("/characters/inject")
def inject(payload: InjectInput):
    bible = CharacterBible(max_characters=ABSOLUTE_MAX_CHARACTERS)
    for c in payload.characters:
        bible.add(Character(name=c.name, description=c.description))
    final_prompt = inject_character_descriptions(payload.scene_prompt, payload.scene_text, bible)
    return {"final_prompt": final_prompt}
