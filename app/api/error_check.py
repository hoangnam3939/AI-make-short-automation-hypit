"""Mục 8, V3 qua API — kiểm tra lỗi kỹ thuật trên các cảnh đã dựng (đường dẫn
file cục bộ, vì app chạy local). Không cần AI key."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import error_checker as ec

router = APIRouter()


class CheckScenesInput(BaseModel):
    scene_paths: list[str] = Field(..., min_length=1)
    expected_width: int
    expected_height: int
    expected_fps: float = 24.0


@router.post("/error-check/scenes")
def check_scenes(payload: CheckScenesInput):
    paths = [Path(p) for p in payload.scene_paths]
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        raise HTTPException(400, f"Không tìm thấy file: {missing}")

    scene_issues = ec.check_resolution_and_fps_consistency(
        paths, payload.expected_width, payload.expected_height, payload.expected_fps,
    )
    return {
        "issues": [
            {"scene_path": str(si.scene_path), "issues": si.issues} for si in scene_issues
        ],
        "ok": len(scene_issues) == 0,
    }


class CheckBlackFrozenInput(BaseModel):
    scene_path: str
    min_black_duration: float = 1.0
    min_freeze_duration: float = 2.0


@router.post("/error-check/black-frozen")
def check_black_frozen(payload: CheckBlackFrozenInput):
    path = Path(payload.scene_path)
    if not path.exists():
        raise HTTPException(400, f"Không tìm thấy file: {payload.scene_path}")

    black = ec.detect_black_frames(path, min_black_duration=payload.min_black_duration)
    frozen = ec.detect_frozen_frames(path, min_freeze_duration=payload.min_freeze_duration)
    return {
        "black_intervals": [{"start": s, "end": e} for s, e in black],
        "frozen_starts": frozen,
        "ok": not black and not frozen,
    }
