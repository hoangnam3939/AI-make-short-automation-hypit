"""Nút "Dự án trước đó" (sidebar, giữa Cài đặt và Đăng bài): lưu lại toàn bộ hiện
trạng 1 dự án (Bước 1-13, kể cả tiến độ sản xuất) ra đĩa, để mở lại ĐÚNG như
lúc đóng app — kể cả sau khi server đã khởi động lại (mất hết `_JOBS` trong
bộ nhớ, xem production_pipeline.py).

Thiết kế cố ý ĐƠN GIẢN — server không hiểu cấu trúc bên trong `data` (đó là
nguyên khối JSON do app.js tự gom lại từ `state` + các ô trên trang), chỉ lo
lưu/đọc lại nguyên vẹn + quản lý danh sách "8 dự án gần nhất". Xoá khỏi danh
sách KHÔNG xoá thư mục `projects/<id>/` (video đã dựng xong không bao giờ bị
xoá tự động qua đường này — chỉ đơn giản không còn hiện trong danh sách xổ
xuống nữa)."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

router = APIRouter()

PROJECTS_DIR = Path(__file__).resolve().parent.parent.parent / "projects"
RECENT_INDEX_PATH = PROJECTS_DIR / "_recent_index.json"
MAX_RECENT = 8
# project_id/language_code đi thẳng vào đường dẫn file — chặn "../" (path
# traversal) ngay từ đầu, không tin tưởng input người dùng dù app chỉ chạy
# local (đúng khuôn crypto.randomUUID() ở app.js: chữ/số/gạch ngang).
_SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,80}$")


def _validated_id(value: str) -> str:
    if not _SAFE_ID_RE.match(value):
        raise HTTPException(400, "Mã dự án/ngôn ngữ không hợp lệ.")
    return value


class ProjectSnapshotInput(BaseModel):
    title: str = Field(..., min_length=1)
    stage_label: str = ""
    data: dict = Field(default_factory=dict)


def _load_recent_index() -> list[dict]:
    if not RECENT_INDEX_PATH.exists():
        return []
    try:
        return json.loads(RECENT_INDEX_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save_recent_index(entries: list[dict]) -> None:
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    RECENT_INDEX_PATH.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


def _upsert_recent_index(project_id: str, title: str, stage_label: str, updated_at: str) -> None:
    entries = [e for e in _load_recent_index() if e.get("project_id") != project_id]
    entries.insert(0, {
        "project_id": project_id, "title": title,
        "stage_label": stage_label, "updated_at": updated_at,
    })
    # Chỉ cắt bớt DANH SÁCH — thư mục projects/<id>/ của dự án bị đẩy ra vẫn
    # còn nguyên trên đĩa, xem docstring module.
    entries = entries[:MAX_RECENT]
    _save_recent_index(entries)


@router.get("/projects/recent")
def list_recent_projects():
    return {"projects": _load_recent_index()}


@router.post("/projects/{project_id}/snapshot")
def save_project_snapshot(project_id: str, payload: ProjectSnapshotInput):
    project_id = _validated_id(project_id)
    project_dir = PROJECTS_DIR / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    updated_at = datetime.now(timezone.utc).isoformat()
    snapshot = {
        "project_id": project_id,
        "title": payload.title,
        "stage_label": payload.stage_label,
        "updated_at": updated_at,
        "data": payload.data,
    }
    (project_dir / "snapshot.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _upsert_recent_index(project_id, payload.title, payload.stage_label, updated_at)
    return {"status": "saved", "updated_at": updated_at}


@router.get("/projects/{project_id}/snapshot")
def get_project_snapshot(project_id: str):
    project_id = _validated_id(project_id)
    snapshot_path = PROJECTS_DIR / project_id / "snapshot.json"
    if not snapshot_path.exists():
        raise HTTPException(404, "Không tìm thấy dự án này.")
    try:
        return json.loads(snapshot_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(500, "File lưu dự án bị hỏng, không đọc được.") from exc


@router.get("/projects/{project_id}/production-files")
def list_production_files(project_id: str):
    """Đường lùi an toàn: video đã dựng xong (final_with_sfx.mp4) luôn tìm
    lại được bằng cách quét thẳng thư mục trên đĩa, KHÔNG phụ thuộc job có
    còn sống trong bộ nhớ server hay không (xem docstring module)."""
    project_id = _validated_id(project_id)
    production_dir = PROJECTS_DIR / project_id / "production"
    results = []
    if production_dir.is_dir():
        for lang_dir in sorted(production_dir.iterdir()):
            if not lang_dir.is_dir():
                continue
            final_path = lang_dir / "final_with_sfx.mp4"
            if not final_path.exists():
                final_path = lang_dir / "final.mp4"
            if final_path.exists():
                stat = final_path.stat()
                results.append({
                    "language_code": lang_dir.name,
                    "size_bytes": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                })
    return {"files": results}


@router.get("/projects/{project_id}/production-files/{language_code}/download")
def download_production_file(project_id: str, language_code: str):
    project_id = _validated_id(project_id)
    language_code = _validated_id(language_code)
    lang_dir = PROJECTS_DIR / project_id / "production" / language_code
    final_path = lang_dir / "final_with_sfx.mp4"
    if not final_path.exists():
        final_path = lang_dir / "final.mp4"
    if not final_path.exists():
        raise HTTPException(404, "Chưa có video hoàn chỉnh cho ngôn ngữ này.")
    return FileResponse(
        final_path, media_type="video/mp4",
        filename=f"video_{project_id}_{language_code}.mp4",
    )
