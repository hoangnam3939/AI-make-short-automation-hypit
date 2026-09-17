"""Bước 9+10+13+12 (Mục 3, V3) nối liền qua API — bấm 1 nút chạy từ "có
prompt cảnh" tới "ra video hoàn chỉnh có SFX + tiêu đề", cho MỌI ngôn ngữ
xuất ra cùng lúc (Bước 3 — cảnh Flow chỉ tạo 1 lần, dùng chung mọi ngôn
ngữ), theo dõi tiến độ qua job_id thay vì phải tự chạy tay từng bước script
như trước (xem app/services/production_pipeline.py)."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.api.project import SUPPORTED_LANGUAGES
from app.services import google_flow_driver
from app.services.production_pipeline import (
    FAILED_SCENE_ACTIONS,
    RUN_MODES,
    SCENE_REVIEW_ACTIONS,
    approve_scene,
    get_job,
    resolve_failed_scene,
    restore_scene,
    set_run_mode,
    start_job,
)
from app.services.sfx_sourcing import SFX_BOOST_DB

router = APIRouter()

PROJECTS_DIR = Path(__file__).resolve().parent.parent.parent / "projects"
_LANGUAGE_NAME_BY_CODE = {lang["code"]: lang["name"] for lang in SUPPORTED_LANGUAGES}


class ScenePromptIn(BaseModel):
    scene_n: int
    prompt: str
    # Bước 8 (Mục 3, V3 — khác với "Bước 8" trong step8_title ở giao diện,
    # vốn là VỊ TRÍ hiển thị "Âm thanh nền" chứ không phải số bước đặc tả
    # gốc): loại hình dựng cho cảnh này, xem storyboard.SCENE_TYPES. Thiếu
    # trường này (dữ liệu cũ) mặc định "ai_video" — hành vi y hệt trước đây.
    scene_type: str = "ai_video"
    chart_data: dict | None = None
    duration_sec: float | None = None
    # Mục 8 (phát hiện nhân vật đổi hình dạng) — văn bản kịch bản gốc của
    # cảnh này, dùng để dò nhân vật nào xuất hiện (xem CharacterIn bên dưới
    # và production_pipeline.py::_check_character_consistency).
    source_text: str = ""


class CharacterIn(BaseModel):
    name: str
    description: str


class BeatIn(BaseModel):
    label: str
    narration_text: str
    scene_ns: list[int]


class ProductionStartInput(BaseModel):
    scenes: list[ScenePromptIn] = Field(..., min_length=1)
    beats: list[BeatIn] = Field(..., min_length=1)
    source_language_code: str = Field(..., description="Ngôn ngữ mà narration_text trong `beats` đang viết")
    language_codes: list[str] = Field(
        ..., min_length=1,
        description="Ngôn ngữ muốn xuất NGAY trong job này (Bước 10 — có thể chỉ chọn 1, hoặc hết tất cả)",
    )
    format: str = "long"
    project_id: str = "default"
    run_mode: str = Field("auto", description=f"1 trong {RUN_MODES} — chế độ chạy Bước 9, đổi được sau khi job đã chạy")
    narration_volume: float = Field(1.8, gt=0, description="Bước 7: hệ số nhân âm lượng lời dẫn")
    sfx_volume_db: float = Field(SFX_BOOST_DB, description="Bước 8: dB cộng thêm vào âm lượng hiệu ứng âm thanh nền")
    include_poster: bool = Field(True, description="Bước 9: có ghép poster mở đầu trước cảnh 1 hay không")
    characters: list[CharacterIn] = Field(
        default_factory=list,
        description="Sổ Tay Nhân Vật (Bước 1) — dùng cho Mục 8 (phát hiện nhân vật đổi hình dạng giữa các cảnh). Rỗng thì bỏ qua kiểm tra này.",
    )


@router.post("/production/open-flow-browser")
def open_flow_browser():
    """Bước 9: mở 1 cửa sổ Chrome thật (không tự động hoá đăng nhập, xem quy
    tắc an toàn trong google_flow_driver.py) để người dùng tự tay đăng nhập
    tài khoản Google Flow/Gemini Pro của họ — thay cho việc phải tự gõ lệnh
    dòng lệnh trong màn hình Help.

    Trả về `already_running`/`brought_to_front` (xem launch_flow_browser())
    để frontend hiển thị đúng thông báo — KHÔNG còn báo "đã mở cửa sổ MỚI"
    một cách vô điều kiện như trước (lỗi thật đã gặp 2026-09-15: bấm lần 2
    trở đi chỉ âm thầm dùng lại cửa sổ Chrome cũ, không mở gì mới, nhưng
    frontend vẫn báo y hệt lần đầu khiến người dùng tưởng nút bị hỏng)."""
    try:
        result = google_flow_driver.launch_flow_browser()
    except google_flow_driver.ChromeNotFoundError as e:
        raise HTTPException(404, str(e))
    except google_flow_driver.FlowBrowserStartTimeout as e:
        raise HTTPException(503, str(e))
    return result


@router.post("/production/start")
def start_production(payload: ProductionStartInput):
    if payload.run_mode not in RUN_MODES:
        raise HTTPException(400, f"run_mode phải là 1 trong {RUN_MODES}")
    beat_of_scene: dict[int, str] = {}
    for beat in payload.beats:
        for sn in beat.scene_ns:
            beat_of_scene[sn] = beat.label
    missing = [s.scene_n for s in payload.scenes if s.scene_n not in beat_of_scene]
    if missing:
        raise HTTPException(400, f"Các cảnh sau không thuộc đoạn nào cả: {missing}")

    beat_order = [b.label for b in payload.beats]
    beat_narration_text = {b.label: b.narration_text for b in payload.beats}
    scene_prompts = [
        {
            "scene_n": s.scene_n, "prompt": s.prompt, "scene_type": s.scene_type,
            "chart_data": s.chart_data, "duration_sec": s.duration_sec, "source_text": s.source_text,
        }
        for s in payload.scenes
    ]
    characters = [{"name": c.name, "description": c.description} for c in payload.characters]

    workdir = PROJECTS_DIR / payload.project_id / "production"
    job_id = start_job(
        scene_prompts=scene_prompts,
        beat_of_scene=beat_of_scene,
        beat_order=beat_order,
        beat_narration_text=beat_narration_text,
        source_language_code=payload.source_language_code,
        language_codes=payload.language_codes,
        language_names=_LANGUAGE_NAME_BY_CODE,
        format_=payload.format,
        workdir=workdir,
        run_mode=payload.run_mode,
        narration_volume=payload.narration_volume,
        sfx_volume_db=payload.sfx_volume_db,
        include_poster=payload.include_poster,
        characters=characters,
    )
    return {"job_id": job_id}


@router.get("/production/{job_id}")
def get_production_status(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(404, "Không tìm thấy job này (có thể server đã khởi động lại).")
    return job.to_dict()


class RunModeInput(BaseModel):
    mode: str = Field(..., description=f"1 trong {RUN_MODES}")


@router.post("/production/{job_id}/mode")
def set_production_mode(job_id: str, payload: RunModeInput):
    """Bước 9: đổi chế độ chạy BẤT CỨ LÚC NÀO trong lúc job đang chạy — áp
    dụng ngay từ cảnh tiếp theo (hoặc cho chạy tiếp ngay nếu đang dừng chờ
    duyệt và đổi sang "auto"). Không cần dừng job lại/chạy lại từ đầu."""
    if get_job(job_id) is None:
        raise HTTPException(404, "Không tìm thấy job này (có thể server đã khởi động lại).")
    try:
        job = set_run_mode(job_id, payload.mode)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return job.to_dict()


@router.post("/production/{job_id}/scenes/{scene_n}/approve")
def approve_production_scene(job_id: str, scene_n: int, action: str = Query("approve")):
    """Chế độ "review": quyết định số phận cảnh `scene_n` đang dừng chờ
    duyệt (xem trước qua GET .../scenes/{scene_n}/video). `action` (query
    param, mặc định "approve") là 1 trong SCENE_REVIEW_ACTIONS: "approve"
    (đồng ý, tạo cảnh tiếp theo), "retry" (tạo lại đúng cảnh này), "skip"
    (bỏ cảnh này khỏi video, sang cảnh tiếp theo)."""
    if action not in SCENE_REVIEW_ACTIONS:
        raise HTTPException(400, f"action phải là 1 trong {SCENE_REVIEW_ACTIONS}, nhận '{action}'")
    if get_job(job_id) is None:
        raise HTTPException(404, "Không tìm thấy job này (có thể server đã khởi động lại).")
    try:
        job = approve_scene(job_id, scene_n, action=action)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return job.to_dict()


@router.post("/production/{job_id}/scenes/{scene_n}/restore")
def restore_production_scene(job_id: str, scene_n: int):
    """Bước 6: khôi phục 1 cảnh "Đã bỏ qua" trở lại video — xem trước qua
    GET .../scenes/{scene_n}/video (nếu `has_video` — xem job.to_dict())
    rồi gọi API này để đồng ý đưa cảnh trở lại. Chỉ hoạt động trong lúc job
    còn đang tạo cảnh, xem production_pipeline.restore_scene()."""
    if get_job(job_id) is None:
        raise HTTPException(404, "Không tìm thấy job này (có thể server đã khởi động lại).")
    try:
        job = restore_scene(job_id, scene_n)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return job.to_dict()


@router.post("/production/{job_id}/scenes/{scene_n}/resolve-failed")
def resolve_failed_production_scene(job_id: str, scene_n: int, action: str = Query(...)):
    """Bước 6: xử lý 1 cảnh "Lỗi" (failed) mà job đã chạy qua rồi (chế độ
    "auto" không dừng lại hỏi ngay như "review") — bấm vào ô cảnh lỗi đó bất
    cứ lúc nào để chọn `action`, 1 trong FAILED_SCENE_ACTIONS: "retry" (tạo
    lại), "skip" (bỏ qua, giữ file cũ nếu có), "delete" (xoá file dở dang
    rồi bỏ qua). Xem production_pipeline.resolve_failed_scene()."""
    if action not in FAILED_SCENE_ACTIONS:
        raise HTTPException(400, f"action phải là 1 trong {FAILED_SCENE_ACTIONS}")
    if get_job(job_id) is None:
        raise HTTPException(404, "Không tìm thấy job này (có thể server đã khởi động lại).")
    try:
        job = resolve_failed_scene(job_id, scene_n, action)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return job.to_dict()


@router.get("/production/{job_id}/scenes/{scene_n}/video")
def get_production_scene_video(job_id: str, scene_n: int):
    """Xem trước clip Flow gốc của 1 cảnh (trước khi ghép giọng đọc/SFX) —
    dùng ở chế độ "review" để người dùng xem rồi mới bấm duyệt."""
    job = get_job(job_id)
    if job is None:
        raise HTTPException(404, "Không tìm thấy job này (có thể server đã khởi động lại).")
    scene = job.scenes.get(scene_n)
    if scene is None or not scene.video_path:
        raise HTTPException(404, f"Cảnh {scene_n} chưa có video để xem trước.")
    return FileResponse(
        scene.video_path, media_type="video/mp4", filename=f"scene_{scene_n:02d}_preview.mp4"
    )


@router.get("/production/{job_id}/video/raw")
def get_production_raw_video(job_id: str):
    """Khung preview (Bước 6-10, 2026-09-14): video cảnh Flow ghép thô theo
    đoạn, CHƯA có lời dẫn/SFX/poster — dùng CHUNG mọi ngôn ngữ (hình ảnh
    không phụ thuộc ngôn ngữ), xem được ngay cả khi các ngôn ngữ vẫn đang dựng."""
    job = get_job(job_id)
    if job is None:
        raise HTTPException(404, "Không tìm thấy job này (có thể server đã khởi động lại).")
    if not job.raw_video_path:
        raise HTTPException(409, "Chưa có cảnh nào dựng xong để xem trước.")
    return FileResponse(job.raw_video_path, media_type="video/mp4", filename=f"raw_{job_id}.mp4")


_VIDEO_STAGE_FIELDS = {
    "narration": ("narration_video_path", "Video ngôn ngữ này chưa lồng xong lời dẫn."),
    "sfx": ("sfx_video_path", "Video ngôn ngữ này chưa lồng xong hiệu ứng âm thanh nền."),
    "final": ("final_video_path", "Video ngôn ngữ này chưa dựng xong."),
}


@router.get("/production/{job_id}/video")
def download_production_video(job_id: str, language_code: str, stage: str = "final"):
    """Khung preview (Bước 6-10): `stage` chọn giai đoạn muốn xem —
    "narration" (có lời dẫn, chưa SFX), "sfx" (có lời dẫn + SFX, chưa
    poster — "sản phẩm hoàn chỉnh" theo cách gọi của người dùng), "final"
    (mặc định, đầy đủ mọi bước kể cả poster nếu Bước 9 chọn có poster)."""
    if stage not in _VIDEO_STAGE_FIELDS:
        raise HTTPException(400, f"stage phải là 1 trong {list(_VIDEO_STAGE_FIELDS)}")
    job = get_job(job_id)
    if job is None:
        raise HTTPException(404, "Không tìm thấy job này (có thể server đã khởi động lại).")
    lang_result = job.languages.get(language_code)
    if lang_result is None:
        raise HTTPException(404, f"Job này không có ngôn ngữ '{language_code}'.")
    field, error_msg = _VIDEO_STAGE_FIELDS[stage]
    video_path = getattr(lang_result, field)
    if not video_path:
        raise HTTPException(409, error_msg)
    return FileResponse(
        video_path, media_type="video/mp4",
        filename=f"video_{job_id}_{language_code}_{stage}.mp4",
    )
