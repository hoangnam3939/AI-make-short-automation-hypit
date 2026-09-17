"""Nối liền Bước 9 (tạo cảnh qua Google Flow) + Bước 10 (dựng video) + Bước 13
(lồng hiệu ứng âm thanh theo từng cảnh) + Bước 12 (tiêu đề/mô tả) thành 1
luồng bấm nút duy nhất, chạy NỀN (thread riêng, không chặn server) — người
dùng theo dõi tiến độ qua `get_job(job_id)` thay vì phải tự chạy tay từng
bước như trước.

Kiến trúc (đúc kết từ việc sửa video Quang Trung thật, xem
.claude/skills/narration-scene-alignment/SKILL.md và sfx-mixing-safety):
1. Sinh từng cảnh qua Google Flow (generate_video_with_retry — tự thử lại,
   tự sửa prompt khi bị từ chối chính sách). 1 cảnh lỗi KHÔNG chặn cả video
   — bị bỏ qua, các cảnh còn lại vẫn tiếp tục. CHỈ LÀM 1 LẦN, dùng chung
   cho MỌI ngôn ngữ xuất ra (hình ảnh không phụ thuộc ngôn ngữ — xem Bước 3
   bên dưới, tránh tốn credit Flow lặp lại vô ích).
2. Gộp cảnh THÀNH CÔNG theo từng đoạn lời dẫn (beat) thành `beat_clip`
   dùng chung cho mọi ngôn ngữ.
3. VỚI TỪNG NGÔN NGỮ xuất ra (Bước 3): dịch lời dẫn nếu khác ngôn ngữ gốc
   (`llm.translate_text`) -> dựng giọng đọc + video từng đoạn bằng
   `build_scene()` (đã sửa: không bao giờ cắt mất cảnh dù giọng đọc ngắn
   hơn video gốc) -> nối thành video hoàn chỉnh -> tính đúng vị trí THỰC SỰ
   hiển thị của từng cảnh (đo bằng ffprobe, KHÔNG dùng độ dài kế hoạch —
   lỗi thật đã gặp: Google Flow luôn trả về clip ~10s bất kể yêu cầu bao
   nhiêu giây) -> nhờ Claude đề xuất lớp âm thanh cho từng cảnh rồi lồng
   vào (Bước 13) -> sinh tiêu đề/mô tả + ghép poster mở đầu (Bước 12).

4. Bước 9 có 2 chế độ chạy, ĐỔI ĐƯỢC BẤT CỨ LÚC NÀO trong lúc job đang chạy
   (không cần dừng job lại chạy lại từ đầu):
   - "auto" (mặc định): tạo cảnh liên tục, không dừng.
   - "review": sau khi 1 cảnh tạo xong (hoặc lỗi), job DỪNG LẠI chờ người
     dùng tự bấm duyệt mới sang cảnh tiếp theo — xem `_wait_for_review_if_needed()`.
   `run_mode` được đọc LẠI TỪ ĐẦU sau mỗi cảnh, nên người dùng có thể đổi
   qua đổi lại nhiều lần giữa chừng (VD: tự động tới cảnh 9 -> đổi sang
   duyệt từng cảnh cho cảnh 10-29 -> đổi lại tự động từ cảnh 30 trở đi) mà
   không cần khởi động lại job. Đổi sang "auto" trong lúc job ĐANG dừng chờ
   duyệt cũng lập tức cho chạy tiếp luôn, không bắt phải bấm duyệt cảnh đó.

5. Bước 6->10 (2026-09-14): Bước 6 hiển thị 37+ cảnh (số lượng tuỳ kịch
   bản) thành 2 hàng ngang song song (hàng cảnh + hàng trạng thái, xem
   app.js::renderProductionScenes) — không có thay đổi backend, chỉ dùng
   lại đúng `job.scenes` đã có. Bước 7 (âm lượng lời dẫn) và Bước 8 (âm
   lượng SFX nền) là 2 tham số `narration_volume`/`sfx_volume_db` đọc 1
   LẦN lúc `start_job()`, áp dụng cho mọi ngôn ngữ của job (không đổi được
   giữa chừng như run_mode). Bước 9 (`include_poster`) tắt việc ghép poster
   mở đầu nếu người dùng chọn "không có poster" — vẫn sinh đủ
   tiêu đề/mô tả/CTA (Bước 12), chỉ bỏ qua ghép ảnh. Bước 10 (xuất 1 ngôn
   ngữ ngay hay xuất hết 1 lần) dùng LUÔN `language_codes` sẵn có — người
   dùng tự chọn ở giao diện muốn gửi những mã nào vào job (không cần thêm
   tham số backend mới); muốn xuất ngôn ngữ còn lại sau thì chạy 1 job MỚI
   với `language_codes` còn lại (job mới hiện vẫn tạo lại cảnh Flow từ đầu
   — CHƯA cache lại cảnh giữa các job, ghi rõ để không ai tưởng nhầm đã
   tối ưu phần này).
"""
from __future__ import annotations

import asyncio
import shutil
import subprocess
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from app.services import error_checker
from app.services import google_flow_driver as flow
from app.services import scene_renderers
from app.services.llm import suggest_sfx_layers, translate_text
from app.services.storyboard import DEFAULT_SCENE_SECONDS
from app.services.quality_review import VideoMetadata, generate_metadata
from app.services.sfx_sourcing import SFX_BOOST_DB, ScenePlan, SfxLayer, apply_step13_sfx, build_sfx_index
from app.services.video_builder import (
    FFPROBE,
    build_scene,
    concat_scenes,
    generate_narration,
    generate_title_card_image,
    image_to_title_clip,
)

TITLE_CARD_DURATION_SEC = 4.0
# Dịch lời dẫn (Bước 3, đa ngôn ngữ) và đề xuất lớp SFX (Bước 13) đều là
# nhiều lượt gọi LLM ĐỘC LẬP với nhau (đoạn A dịch/cảnh A không cần biết
# đoạn B/cảnh B) — chạy song song thay vì tuần tự, cùng tinh thần đã sửa
# cho sinh prompt cảnh (xem storyboard.MAX_CONCURRENT_SCENE_PROMPT_CALLS).
#
# Giữ CÙNG mức 2 như storyboard.MAX_CONCURRENT_SCENE_PROMPT_CALLS (xem lý
# do đầy đủ ở đó: máy dev thật chỉ 4 lõi CPU + thường ~2GB RAM trống, backend
# CLI mỗi luồng tự mở 1 tiến trình Node.js riêng, 4 luồng cùng lúc từng bị
# timeout thật) — không đặt cao hơn 2 dù về mặt logic 2 việc này độc lập
# nhau, vì nút thắt là PHẦN CỨNG chạy CLI, không phải bản thân thuật toán.
MAX_CONCURRENT_TRANSLATE_CALLS = 2
MAX_CONCURRENT_SFX_SUGGEST_CALLS = 2


def _probe_duration(path: Path) -> float:
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


@dataclass
class SceneProgress:
    scene_n: int
    status: str = "queued"  # queued | generating | done | failed | skipped
    error: str | None = None
    video_path: str | None = None
    # Bước 8 (Mục 3, V3): loại hình đã quyết định cho cảnh này lúc sinh
    # prompt — chỉ để HIỂN THỊ trên giao diện (icon cạnh số cảnh), không ảnh
    # hưởng logic tạo cảnh (xem scene_renderers.py).
    scene_type: str = "ai_video"
    # Giữ lại nguyên liệu để dựng lại — cần cho restore_scene() (khôi phục 1
    # cảnh đã "Bỏ qua" mà không phải lưu lại toàn bộ scene_prompts gốc trên job.
    prompt: str = ""
    chart_data: dict | None = None
    duration_sec: float | None = None
    # Đếm số lần đã tạo lại nền (restore_scene()/resolve_failed_scene() với
    # action="retry") — dùng để đặt tên thư mục tải về riêng cho mỗi lần,
    # tránh đè lẫn nhau khi người dùng bấm tạo lại nhiều lần liên tiếp.
    regen_attempts: int = 0


@dataclass
class LanguageResult:
    language_code: str
    status: str = "queued"  # queued | translating | building_video | adding_sfx | adding_title | done | failed
    error: str | None = None
    final_video_path: str | None = None
    # Khung preview bên phải (2026-09-14, xem app.js::renderPreviewPanel):
    # video TRUNG GIAN của từng giai đoạn, giữ NGUYÊN không bị đè khi bước
    # sau chạy (mỗi bước ghi ra 1 file riêng — xem _run_one_language) để
    # người dùng xem được cả "chưa lồng tiếng" / "có lời dẫn" / "có lời dẫn
    # + SFX" trong lúc video vẫn đang được sản xuất tiếp, không cần đợi
    # xong hẳn mới xem được.
    narration_video_path: str | None = None  # có lời dẫn, CHƯA có SFX/poster
    sfx_video_path: str | None = None  # có lời dẫn + SFX, CHƯA có poster
    metadata: VideoMetadata | None = None

    def to_dict(self) -> dict:
        return {
            "language_code": self.language_code,
            "status": self.status,
            "error": self.error,
            "final_video_path": self.final_video_path,
            "narration_video_available": self.narration_video_path is not None,
            "sfx_video_available": self.sfx_video_path is not None,
            "metadata": (
                {
                    "titles": self.metadata.titles,
                    "subtitle": self.metadata.subtitle,
                    "descriptions": self.metadata.descriptions,
                    "cta_texts": self.metadata.cta_texts,
                    "thumbnail_texts": self.metadata.thumbnail_texts,
                }
                if self.metadata
                else None
            ),
        }


RUN_MODES = ("auto", "review")
# Bước 9 (2026-09-14): 3 lựa chọn khi job dừng chờ duyệt 1 cảnh — "approve"
# (đồng ý, tạo cảnh tiếp theo), "retry" (tạo lại đúng cảnh này, không sang
# cảnh kế), "skip" (bỏ cảnh này khỏi video, sang cảnh kế). Xem approve_scene()
# và _generate_scenes().
SCENE_REVIEW_ACTIONS = ("approve", "retry", "skip")


@dataclass
class ProductionJob:
    job_id: str
    scenes: dict[int, SceneProgress] = field(default_factory=dict)
    languages: dict[str, LanguageResult] = field(default_factory=dict)
    status: str = "queued"  # queued | generating_scenes | translating | building_languages | done | failed
    error: str | None = None
    # Bước 9, 2 chế độ (xem docstring module) — đổi được bất cứ lúc nào.
    run_mode: str = "auto"  # "auto" | "review"
    awaiting_review_scene: int | None = None  # scene_n đang dừng chờ duyệt, None = không dừng
    # Khung preview: video cảnh Flow ghép thô theo đoạn (KHÔNG có lời dẫn/SFX
    # — hình ảnh không phụ thuộc ngôn ngữ nên dùng CHUNG cho mọi ngôn ngữ,
    # xem docstring module mục 1-2).
    raw_video_path: str | None = None
    # Bước 7/8/9 (2026-09-14): tuỳ chỉnh trước khi bấm "Bắt đầu sản xuất",
    # áp dụng cho MỌI ngôn ngữ của job này (không đổi được giữa chừng như
    # run_mode — đọc 1 lần lúc bắt đầu job).
    narration_volume: float = 1.8  # nhân thẳng vào giọng đọc, xem sfx_sourcing.mix_layers_into_video
    sfx_volume_db: float = SFX_BOOST_DB  # cộng thêm vào gain riêng từng lớp SFX
    include_poster: bool = True  # Bước 9: có ghép poster mở đầu trước cảnh 1 hay không
    # Mục 8: cảnh báo CHẤT LƯỢNG (nhân vật đổi hình dạng, giọng đọc lệch thời
    # gian, chữ poster lỗi) — chỉ để hiển thị, không chặn/ảnh hưởng gì tới
    # video đã dựng xong (xem _check_character_consistency, error_checker.py).
    quality_warnings: list[str] = field(default_factory=list)
    # Cần cho restore_scene() — dựng lại đúng nơi/đúng định dạng khi khôi phục
    # 1 cảnh đã "Bỏ qua" mà chưa từng có video (xem start_job()).
    workdir: Path | None = None
    format_: str = "long"
    _resume_event: threading.Event = field(default_factory=threading.Event, repr=False, compare=False)
    # Hành động người dùng chọn ở banner duyệt cảnh — đọc bởi _wait_for_review_if_needed()
    # ngay sau khi _resume_event được set (xem approve_scene()).
    _review_action: str = field(default="approve", repr=False, compare=False)

    def to_dict(self) -> dict:
        done = sum(1 for s in self.scenes.values() if s.status == "done")
        failed = sum(1 for s in self.scenes.values() if s.status == "failed")
        return {
            "job_id": self.job_id,
            "status": self.status,
            "error": self.error,
            "scenes_total": len(self.scenes),
            "scenes_done": done,
            "scenes_failed": failed,
            "run_mode": self.run_mode,
            "awaiting_review_scene": self.awaiting_review_scene,
            "narration_volume": self.narration_volume,
            "sfx_volume_db": self.sfx_volume_db,
            "include_poster": self.include_poster,
            "quality_warnings": self.quality_warnings,
            "raw_video_available": self.raw_video_path is not None,
            "scenes": {
                str(sn): {
                    "status": sp.status, "error": sp.error, "scene_type": sp.scene_type,
                    # Bước 6: cho frontend biết cảnh "Đã bỏ qua" có sẵn video cũ để
                    # xem lại ngay không (skip SAU KHI tạo xong) hay phải tạo lại từ
                    # đầu khi khôi phục (skip SAU KHI lỗi — xem restore_scene()).
                    "has_video": sp.video_path is not None,
                }
                for sn, sp in sorted(self.scenes.items())
            },
            "languages": {lc: lr.to_dict() for lc, lr in self.languages.items()},
        }


_JOBS: dict[str, ProductionJob] = {}


def get_job(job_id: str) -> ProductionJob | None:
    return _JOBS.get(job_id)


def set_run_mode(job_id: str, mode: str) -> ProductionJob:
    """Đổi chế độ chạy Bước 9 — gọi được BẤT CỨ LÚC NÀO trong lúc job đang
    chạy, áp dụng ngay cho cảnh tiếp theo. Nếu đang đổi sang "auto" trong
    lúc job ĐANG dừng chờ duyệt 1 cảnh, cho chạy tiếp luôn ngay lập tức —
    không bắt người dùng phải bấm duyệt cảnh đó nữa."""
    if mode not in RUN_MODES:
        raise ValueError(f"mode phải là 1 trong {RUN_MODES}, nhận '{mode}'")
    job = _JOBS.get(job_id)
    if job is None:
        raise KeyError(job_id)
    job.run_mode = mode
    if mode == "auto" and job.awaiting_review_scene is not None:
        job._resume_event.set()
    return job


def approve_scene(job_id: str, scene_n: int, action: str = "approve") -> ProductionJob:
    """Chế độ "review": quyết định số phận cảnh `scene_n` đang dừng chờ
    duyệt. `action` là 1 trong SCENE_REVIEW_ACTIONS: "approve" (đồng ý, tạo
    cảnh tiếp theo), "retry" (tạo lại đúng cảnh này), "skip" (bỏ cảnh này
    khỏi video, sang cảnh tiếp theo). Chỉ có tác dụng nếu job ĐANG dừng chờ
    đúng cảnh này."""
    if action not in SCENE_REVIEW_ACTIONS:
        raise ValueError(f"action phải là 1 trong {SCENE_REVIEW_ACTIONS}, nhận '{action}'")
    job = _JOBS.get(job_id)
    if job is None:
        raise KeyError(job_id)
    if job.awaiting_review_scene != scene_n:
        raise ValueError(
            f"Job không đang dừng chờ duyệt cảnh {scene_n} "
            f"(hiện đang chờ: {job.awaiting_review_scene})."
        )
    job._review_action = action
    job._resume_event.set()
    return job


def restore_scene(job_id: str, scene_n: int) -> ProductionJob:
    """Khôi phục 1 cảnh đang ở trạng thái "Đã bỏ qua" (skipped) trở lại
    video, theo yêu cầu người dùng ở Bước 6 (bấm vào 1 ô cảnh "Đã bỏ qua"
    để xem lại hoặc đồng ý đưa lại vào video).

    2 trường hợp:
    - Cảnh từng tạo THÀNH CÔNG rồi mới bị bỏ qua (người dùng đổi ý sau khi
      xem trước) — `video_path` vẫn còn nguyên (skip không xoá), khôi phục
      ngay lập tức, không cần tạo lại.
    - Cảnh bị lỗi rồi mới bị bỏ qua — chưa từng có video, phải tạo lại
      giống hệt logic "retry" trong _generate_scenes(), chạy NỀN (thread
      riêng) để không chặn request; job.scenes[scene_n] tạm chuyển sang
      "generating" trong lúc chờ.

    CHỈ hoạt động trong lúc job còn ở bước tạo cảnh (`status ==
    "generating_scenes"`) — _build_beat_clips() chỉ chạy ĐÚNG 1 LẦN ngay
    sau khi vòng lặp tạo cảnh xong, nên khôi phục sau thời điểm đó sẽ không
    kịp vào video cuối (đã ghép xong theo đoạn) — cần chạy 1 job sản xuất
    mới nếu muốn thêm cảnh đó vào lúc này."""
    job = _JOBS.get(job_id)
    if job is None:
        raise KeyError(job_id)
    if job.status != "generating_scenes":
        raise ValueError(
            "Chỉ khôi phục được cảnh trong lúc job đang ở bước tạo cảnh (Bước 6) — "
            "job này đã sang bước dựng video, cần chạy job sản xuất mới để đưa lại cảnh này."
        )
    scene = job.scenes.get(scene_n)
    if scene is None or scene.status != "skipped":
        raise ValueError(f"Cảnh {scene_n} hiện không ở trạng thái 'Đã bỏ qua'.")

    if scene.video_path:
        scene.status = "done"
        scene.error = None
        return job

    _regenerate_scene_in_background(job, scene, scene_n, fail_status="skipped", fail_prefix="Khôi phục thất bại")
    return job


FAILED_SCENE_ACTIONS = ("retry", "skip", "delete")


def resolve_failed_scene(job_id: str, scene_n: int, action: str) -> ProductionJob:
    """Bước 6: xử lý 1 cảnh đang ở trạng thái "Lỗi" (failed) mà job đã chạy
    qua rồi mà KHÔNG dừng lại hỏi ngay lúc đó (chế độ "auto" — khác chế độ
    "review", nơi lỗi/xong 1 cảnh đều dừng lại chờ duyệt ngay). Người dùng
    bấm vào ô cảnh lỗi đó bất cứ lúc nào sau đó (trong lúc job vẫn đang tạo
    các cảnh khác) để quyết định:
    - "retry": tạo lại đúng cảnh này (chạy nền, không chặn request).
    - "skip": bỏ qua, giữ nguyên file dở dang trên đĩa (nếu có), không đưa
      vào video cuối.
    - "delete": XOÁ file/thư mục tải về dở dang của cảnh này (dọn đĩa) rồi
      bỏ qua, không đưa vào video cuối.

    CHỈ hoạt động trong lúc job còn ở bước tạo cảnh (status ==
    "generating_scenes") — cùng lý do với restore_scene() (_build_beat_clips
    chỉ ghép ĐÚNG 1 LẦN ngay sau khi vòng lặp tạo cảnh xong)."""
    if action not in FAILED_SCENE_ACTIONS:
        raise ValueError(f"action phải là 1 trong {FAILED_SCENE_ACTIONS}, nhận '{action}'")
    job = _JOBS.get(job_id)
    if job is None:
        raise KeyError(job_id)
    if job.status != "generating_scenes":
        raise ValueError(
            "Chỉ xử lý được cảnh lỗi trong lúc job đang ở bước tạo cảnh (Bước 6) — "
            "job này đã sang bước dựng video, cần chạy job sản xuất mới."
        )
    scene = job.scenes.get(scene_n)
    if scene is None or scene.status != "failed":
        raise ValueError(f"Cảnh {scene_n} hiện không ở trạng thái 'Lỗi'.")

    if action == "skip":
        scene.status = "skipped"
        return job
    if action == "delete":
        _delete_scene_downloads(job, scene_n)
        scene.status = "skipped"
        scene.error = None
        return job

    # action == "retry"
    _regenerate_scene_in_background(job, scene, scene_n, fail_status="failed", fail_prefix="Tạo lại thất bại")
    return job


def _regenerate_scene_in_background(
    job: ProductionJob, scene: SceneProgress, scene_n: int, fail_status: str, fail_prefix: str,
) -> None:
    """Dùng chung cho restore_scene() (cảnh "Đã bỏ qua" chưa từng có video)
    và resolve_failed_scene() action="retry" — tạo lại 1 cảnh NGOÀI vòng lặp
    chính của _generate_scenes(), chạy nền (thread riêng) để không chặn
    request. `fail_status` là trạng thái gán lại nếu lần tạo lại này VẪN lỗi
    ("skipped" cho restore — coi như giữ nguyên quyết định bỏ qua trước đó;
    "failed" cho resolve_failed_scene — vẫn là lỗi, người dùng bấm lại được)."""
    scene.status = "generating"
    scene.error = None
    scene.regen_attempts += 1
    attempt = scene.regen_attempts

    def _regenerate() -> None:
        out_dir = job.workdir / "downloads" / f"scene_{scene_n:02d}_regen{attempt}"
        try:
            path = scene_renderers.render_scene(
                scene.scene_type, scene.prompt, scene.duration_sec or DEFAULT_SCENE_SECONDS,
                job.format_, out_dir, scene.chart_data,
            )
            scene.status = "done"
            scene.video_path = str(path)
        except Exception as exc:  # noqa: BLE001 - tạo lại lỗi không được làm crash job chính
            scene.status = fail_status
            scene.error = f"{fail_prefix}: {exc}"

    threading.Thread(target=_regenerate, daemon=True).start()


def _delete_scene_downloads(job: ProductionJob, scene_n: int) -> None:
    """Xoá mọi thư mục/file tải về đã tạo cho 1 cảnh (kể cả các lần thử lại
    trước đó) — dùng khi người dùng chủ động chọn "Xoá file đã tạo" cho 1
    cảnh lỗi, dọn đĩa khỏi các file dở dang không dùng được nữa."""
    downloads_dir = job.workdir / "downloads" if job.workdir else None
    if not downloads_dir or not downloads_dir.exists():
        return
    prefix = f"scene_{scene_n:02d}"
    for entry in downloads_dir.iterdir():
        if entry.name != prefix and not entry.name.startswith(f"{prefix}_"):
            continue
        try:
            if entry.is_dir():
                shutil.rmtree(entry, ignore_errors=True)
            else:
                entry.unlink(missing_ok=True)
        except OSError:
            pass


def _wait_for_review_if_needed(job: ProductionJob, scene_n: int) -> str:
    """Sau khi 1 cảnh tạo xong (hoặc lỗi): nếu đang ở chế độ "review", dừng
    lại chờ `approve_scene()` hoặc `set_run_mode(job_id, "auto")` mở khoá.
    `run_mode` đọc TẠI THỜI ĐIỂM cảnh này vừa xong — cho phép đổi chế độ
    qua lại nhiều lần giữa chừng mà không cần khởi động lại job. Trả về
    hành động đã chọn ("approve" mặc định khi không ở chế độ review, hoặc
    khi bị mở khoá qua đổi sang "auto")."""
    if job.run_mode != "review":
        return "approve"
    job._resume_event.clear()
    job._review_action = "approve"
    job.awaiting_review_scene = scene_n
    job._resume_event.wait()
    job.awaiting_review_scene = None
    return job._review_action


def start_job(
    scene_prompts: list[dict],
    beat_of_scene: dict[int, str],
    beat_order: list[str],
    beat_narration_text: dict[str, str],
    source_language_code: str,
    language_codes: list[str],
    language_names: dict[str, str],
    format_: str,
    workdir: Path,
    run_mode: str = "auto",
    narration_volume: float = 1.8,
    sfx_volume_db: float = SFX_BOOST_DB,
    include_poster: bool = True,
    characters: list[dict] | None = None,
) -> str:
    """Bắt đầu 1 job sản xuất video nền. `scene_prompts`: list các
    {scene_n, prompt} (thứ tự bất kỳ). `beat_of_scene`: scene_n -> tên đoạn.
    `beat_order`: thứ tự các đoạn trong video. `beat_narration_text`: tên
    đoạn -> toàn văn lời dẫn của đoạn đó, viết bằng `source_language_code`.
    `language_codes`: NGÔN NGỮ muốn xuất ra NGAY trong job này (Bước 10 có
    thể chọn xuất trước 1 ngôn ngữ rồi chạy job khác sau cho ngôn ngữ còn
    lại, hoặc xuất hết 1 lần) — cảnh Flow chỉ tạo 1 lần dùng chung; ngôn ngữ
    khác `source_language_code` sẽ được tự dịch lời dẫn trước khi dựng.
    `language_names`: mã ngôn ngữ -> tên (dùng cho prompt dịch, VD "vi-VN"
    -> "Tiếng Việt"). `run_mode`: "auto" (mặc định) hoặc "review" (Bước 9,
    dừng chờ duyệt sau mỗi cảnh) — đổi được bất cứ lúc nào sau đó qua
    `set_run_mode()`, không chỉ lúc bắt đầu. `narration_volume` (Bước 7),
    `sfx_volume_db` (Bước 8), `include_poster` (Bước 9): đọc 1 lần lúc bắt
    đầu job, áp dụng cho mọi ngôn ngữ của job này. `characters`: Sổ Tay Nhân
    Vật (Bước 1, [{"name":..., "description":...}]) — dùng cho Mục 8 (phát
    hiện nhân vật đổi hình dạng); rỗng/None thì bỏ qua kiểm tra này."""
    if run_mode not in RUN_MODES:
        raise ValueError(f"run_mode phải là 1 trong {RUN_MODES}, nhận '{run_mode}'")
    job = ProductionJob(
        job_id=uuid.uuid4().hex[:12], run_mode=run_mode,
        narration_volume=narration_volume, sfx_volume_db=sfx_volume_db, include_poster=include_poster,
        workdir=workdir, format_=format_,
    )
    for sp in scene_prompts:
        job.scenes[sp["scene_n"]] = SceneProgress(
            scene_n=sp["scene_n"], scene_type=sp.get("scene_type", "ai_video"),
            prompt=sp["prompt"], chart_data=sp.get("chart_data"), duration_sec=sp.get("duration_sec"),
        )
    for lc in language_codes:
        job.languages[lc] = LanguageResult(language_code=lc)
    _JOBS[job.job_id] = job

    t = threading.Thread(
        target=_run_pipeline,
        args=(
            job, scene_prompts, beat_of_scene, beat_order, beat_narration_text,
            source_language_code, language_codes, language_names, format_, workdir,
            characters or [],
        ),
        daemon=True,
    )
    t.start()
    return job.job_id


def _run_pipeline(
    job: ProductionJob,
    scene_prompts: list[dict],
    beat_of_scene: dict[int, str],
    beat_order: list[str],
    beat_narration_text: dict[str, str],
    source_language_code: str,
    language_codes: list[str],
    language_names: dict[str, str],
    format_: str,
    workdir: Path,
    characters: list[dict] | None = None,
) -> None:
    try:
        _generate_scenes(job, scene_prompts, workdir, format_)
        _check_character_consistency(job, scene_prompts, characters or [], workdir)
        beat_clip_paths = _build_beat_clips(job, scene_prompts, beat_of_scene, beat_order, workdir)
        if not beat_clip_paths:
            raise RuntimeError("Không có cảnh nào tạo thành công — không thể dựng video.")
        # Khung preview: ghép sẵn 1 bản "chưa có lời dẫn" dùng chung mọi ngôn
        # ngữ — cho người dùng xem được ngay cả khi các ngôn ngữ vẫn đang dựng.
        raw_clips = [beat_clip_paths[b] for b in beat_order if b in beat_clip_paths]
        if raw_clips:
            job.raw_video_path = str(concat_scenes(raw_clips, workdir / "raw_preview.mp4"))

        job.status = "translating"
        lang_text_by_lang = _translate_all_beats(
            beat_narration_text, language_codes, source_language_code, language_names,
        )

        job.status = "building_languages"
        for lang in language_codes:
            _run_one_language(
                job, lang, beat_order, beat_clip_paths, lang_text_by_lang[lang],
                scene_prompts, beat_of_scene, format_, workdir / lang,
            )

        job.status = "done" if any(lr.status == "done" for lr in job.languages.values()) else "failed"
    except Exception as exc:  # noqa: BLE001 - job lỗi phải ghi lại rõ ràng cho người dùng thấy, không được im lặng chết
        job.status = "failed"
        job.error = str(exc)


def _check_character_consistency(
    job: ProductionJob, scene_prompts: list[dict], characters: list[dict], workdir: Path,
) -> None:
    """Mục 8, phần 1 (cốt lõi/độc quyền): phát hiện nhân vật đổi hình dạng
    giữa các cảnh (xem character_consistency.py). Bỏ qua ngay nếu chưa có
    Sổ Tay Nhân Vật (`characters` rỗng — hiện tại giao diện LUÔN gửi rỗng vì
    chưa có màn hình nhập Bước 1, xem app/static/app.js). Lỗi ở đây (thiếu
    torch/open-clip-torch, model CLIP tải lỗi...) chỉ ghi 1 cảnh báo, KHÔNG
    được làm hỏng cả job — đây là tính năng CẢNH BÁO THÊM, không phải bước
    bắt buộc để có video."""
    if not characters:
        return
    try:
        from app.services import character_consistency
        from app.services.character_bible import ABSOLUTE_MAX_CHARACTERS, Character, CharacterBible

        bible = CharacterBible(max_characters=ABSOLUTE_MAX_CHARACTERS)
        for c in characters:
            bible.add(Character(name=c["name"], description=c["description"]))

        scene_source_texts = {sp["scene_n"]: sp.get("source_text", "") for sp in scene_prompts}
        done_video_paths = {
            sn: sp.video_path for sn, sp in job.scenes.items() if sp.status == "done" and sp.video_path
        }
        if not done_video_paths:
            return
        embeddings = character_consistency.build_scene_embeddings(done_video_paths, workdir / "consistency")
        warnings = character_consistency.check_character_consistency(scene_source_texts, embeddings, bible)
        job.quality_warnings.extend(w.message() for w in warnings)
    except Exception as exc:  # noqa: BLE001 - cảnh báo thêm, không được chặn cả job
        job.quality_warnings.append(f"Không chạy được kiểm tra nhân vật đổi hình dạng (Mục 8): {exc}")


def _check_narration_drift(
    job: ProductionJob,
    lang: str,
    beat_order: list[str],
    scene_build_paths: list[Path],
    scene_prompts: list[dict],
    beat_of_scene: dict[int, str],
) -> None:
    """Mục 8, phần 2: giọng đọc lệch thời gian so với kế hoạch storyboard
    (xem error_checker.check_narration_scene_drift — không dùng ffsubsync,
    xem docstring module đó). `scene_build_paths` cùng thứ tự `beat_order`
    (xem _build_beat_scenes); thời lượng dự kiến mỗi đoạn = tổng
    `duration_sec` các cảnh thuộc đoạn đó."""
    try:
        planned_by_beat: dict[str, float] = {b: 0.0 for b in beat_order}
        for sp in scene_prompts:
            beat = beat_of_scene.get(sp["scene_n"])
            if beat in planned_by_beat and sp.get("duration_sec"):
                planned_by_beat[beat] += float(sp["duration_sec"])
        planned_durations = [planned_by_beat[b] for b in beat_order]
        warnings = error_checker.check_narration_scene_drift(scene_build_paths, planned_durations)
        job.quality_warnings.extend(f"[{lang}] {w}" for w in warnings)
    except Exception as exc:  # noqa: BLE001 - cảnh báo thêm, không được chặn cả job
        job.quality_warnings.append(f"[{lang}] Không chạy được kiểm tra giọng đọc lệch thời gian (Mục 8): {exc}")


def _translate_all_beats(
    beat_narration_text: dict[str, str],
    language_codes: list[str],
    source_language_code: str,
    language_names: dict[str, str],
) -> dict[str, dict[str, str]]:
    """Dịch lời dẫn từng đoạn (beat) sang từng ngôn ngữ xuất thêm — chạy
    SONG SONG mọi cặp (ngôn ngữ, đoạn) cần dịch cùng lúc thay vì tuần tự
    từng đoạn rồi tuần tự từng ngôn ngữ (lỗi thật: kịch bản 8 đoạn x 2 ngôn
    ngữ cần dịch = 16 lượt gọi CLI tuần tự, mỗi lượt 20-60s, có thể mất hơn
    10 phút CHỈ để dịch trước khi bắt đầu dựng video — cùng bệnh với sinh
    prompt cảnh, xem storyboard.MAX_CONCURRENT_SCENE_PROMPT_CALLS).

    translate_text() tự nuốt lỗi và trả về nguyên văn gốc nếu dịch thất bại
    (xem docstring của nó trong llm.py) nên KHÔNG cần logic báo lỗi sớm như
    sinh prompt cảnh — 1 cặp dịch lỗi không chặn các cặp khác, chỉ âm thầm
    giữ nguyên văn gốc cho đúng đoạn/ngôn ngữ đó."""
    result: dict[str, dict[str, str]] = {}
    tasks: list[tuple[str, str]] = []  # (lang, beat) cần dịch thật sự
    for lang in language_codes:
        if lang == source_language_code:
            result[lang] = beat_narration_text
        else:
            result[lang] = {}
            tasks.extend((lang, beat) for beat in beat_narration_text)

    if not tasks:
        return result

    def _translate_one(lang: str, beat: str) -> str:
        return translate_text(beat_narration_text[beat], language_names.get(lang, lang))

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_TRANSLATE_CALLS) as executor:
        future_to_task = {executor.submit(_translate_one, lang, beat): (lang, beat) for lang, beat in tasks}
        for future, (lang, beat) in future_to_task.items():
            result[lang][beat] = future.result()

    return result


def _run_one_language(
    job: ProductionJob,
    lang: str,
    beat_order: list[str],
    beat_clip_paths: dict[str, Path],
    lang_text: dict[str, str],
    scene_prompts: list[dict],
    beat_of_scene: dict[int, str],
    format_: str,
    workdir: Path,
) -> None:
    lang_result = job.languages[lang]
    try:
        lang_result.status = "building_video"
        scene_build_paths = _build_beat_scenes(beat_order, beat_clip_paths, lang_text, lang, format_, workdir)
        final_path = concat_scenes(scene_build_paths, workdir / "final.mp4")
        lang_result.narration_video_path = str(final_path)
        _check_narration_drift(job, lang, beat_order, scene_build_paths, scene_prompts, beat_of_scene)

        lang_result.status = "adding_sfx"
        out_final = _apply_sfx(job, final_path, scene_prompts, beat_of_scene, beat_order, scene_build_paths, workdir)
        lang_result.sfx_video_path = str(out_final)

        lang_result.status = "adding_title"
        out_with_title, metadata = _add_title_card(
            job, out_final, beat_order, lang_text, format_, workdir, include_poster=job.include_poster
        )
        lang_result.metadata = metadata

        lang_result.final_video_path = str(out_with_title)
        lang_result.status = "done"
    except Exception as exc:  # noqa: BLE001 - 1 ngôn ngữ lỗi không nên chặn các ngôn ngữ khác
        lang_result.status = "failed"
        lang_result.error = str(exc)


def _generate_scenes(job: ProductionJob, scene_prompts: list[dict], workdir: Path, format_: str = "long") -> None:
    """Bước 8: mỗi cảnh dựng qua ĐÚNG loại hình đã quyết định lúc sinh prompt
    (`sp["scene_type"]`, xem storyboard.generate_scene_prompts) — dispatch
    qua scene_renderers.render_scene(), không còn gọi thẳng Flow cho mọi
    cảnh như trước. `sp` thiếu "scene_type" (dữ liệu cũ trước Bước 8) mặc
    định về "ai_video" — hành vi y hệt trước khi thêm Bước 8."""
    job.status = "generating_scenes"
    downloads_dir = workdir / "downloads"
    i = 0
    while i < len(scene_prompts):
        sp = scene_prompts[i]
        sn = sp["scene_n"]
        scene_type = sp.get("scene_type", "ai_video")
        chart_data = sp.get("chart_data")
        duration_sec = sp.get("duration_sec") or DEFAULT_SCENE_SECONDS
        attempt = 1
        while True:
            job.scenes[sn].status = "generating"
            job.scenes[sn].error = None
            try:
                # attempt > 1 = đang "tạo lại" (retry) — dùng thư mục tải riêng
                # để không lẫn với clip cũ của lần tạo trước.
                out_dir = downloads_dir / f"scene_{sn:02d}" if attempt == 1 else downloads_dir / f"scene_{sn:02d}_retry{attempt}"
                path = scene_renderers.render_scene(scene_type, sp["prompt"], duration_sec, format_, out_dir, chart_data)
                job.scenes[sn].status = "done"
                job.scenes[sn].video_path = str(path)
            except Exception as exc:  # noqa: BLE001 - 1 cảnh lỗi không được chặn cả video, xem docstring module
                job.scenes[sn].status = "failed"
                job.scenes[sn].error = str(exc)
            action = _wait_for_review_if_needed(job, sn)
            if action == "retry":
                attempt += 1
                continue  # tạo lại đúng cảnh này, chưa sang cảnh kế tiếp
            if action == "skip":
                job.scenes[sn].status = "skipped"
            break
        i += 1


def _build_beat_clips(
    job: ProductionJob,
    scene_prompts: list[dict],
    beat_of_scene: dict[int, str],
    beat_order: list[str],
    workdir: Path,
) -> dict[str, Path]:
    """Ghép cảnh Flow THÀNH CÔNG theo từng đoạn — KHÔNG phụ thuộc ngôn ngữ,
    dùng chung cho mọi ngôn ngữ xuất ra ở bước sau (xem docstring module)."""
    scenes_by_beat: dict[str, list[int]] = {b: [] for b in beat_order}
    for sp in scene_prompts:
        sn = sp["scene_n"]
        if job.scenes[sn].status == "done":
            scenes_by_beat[beat_of_scene[sn]].append(sn)
    for b in scenes_by_beat:
        scenes_by_beat[b].sort()

    beat_clip_paths: dict[str, Path] = {}
    beat_clips_dir = workdir / "beat_clips"
    for beat in beat_order:
        sns = scenes_by_beat[beat]
        if not sns:
            continue
        clip_paths = [Path(job.scenes[sn].video_path) for sn in sns]
        out_path = beat_clips_dir / f"{beat}.mp4"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if len(clip_paths) == 1:
            out_path.write_bytes(clip_paths[0].read_bytes())
        else:
            concat_scenes(clip_paths, out_path)
        beat_clip_paths[beat] = out_path
    return beat_clip_paths


def _build_beat_scenes(
    beat_order: list[str],
    beat_clip_paths: dict[str, Path],
    beat_narration_text: dict[str, str],
    language_code: str,
    format_: str,
    workdir: Path,
) -> list[Path]:
    scene_build_paths: list[Path] = []
    for i, beat in enumerate(beat_order, start=1):
        if beat not in beat_clip_paths:
            continue
        audio_path = workdir / "audio" / f"scene_{i:02d}.mp3"
        asyncio.run(generate_narration(beat_narration_text.get(beat, ""), language_code, audio_path))
        scene_out = workdir / "build" / f"scene_{i:02d}.mp4"
        build_scene(audio_path, scene_out, video_path=beat_clip_paths[beat], format_=format_)
        scene_build_paths.append(scene_out)
    return scene_build_paths


def _apply_sfx(
    job: ProductionJob,
    final_path: Path,
    scene_prompts: list[dict],
    beat_of_scene: dict[int, str],
    beat_order: list[str],
    scene_build_paths: list[Path],
    workdir: Path,
) -> Path:
    """Tính đúng vị trí THỰC SỰ hiển thị của từng cảnh trong video cuối (đo
    bằng ffprobe trên chính từng clip Flow đã tải và từng đoạn đã dựng —
    KHÔNG dùng độ dài kế hoạch, xem lỗi thật đã gặp trong skill
    narration-scene-alignment), rồi nhờ Claude đề xuất + lồng SFX theo từng
    cảnh (Bước 13)."""
    prompt_of = {sp["scene_n"]: sp["prompt"] for sp in scene_prompts}
    real_dur_of = {
        sn: _probe_duration(Path(job.scenes[sn].video_path))
        for sn in job.scenes
        if job.scenes[sn].status == "done"
    }

    scenes_by_beat: dict[str, list[int]] = {b: [] for b in beat_order}
    for sn, beat in beat_of_scene.items():
        if job.scenes.get(sn) and job.scenes[sn].status == "done":
            scenes_by_beat[beat].append(sn)
    for b in scenes_by_beat:
        scenes_by_beat[b].sort()

    beat_durs = [_probe_duration(p) for p in scene_build_paths]
    beats_with_clips = [b for b in beat_order if scenes_by_beat[b]]

    visible: list[tuple[int, float, float]] = []
    cum_beat_offset = 0.0
    for bi, beat in enumerate(beats_with_clips):
        final_dur = beat_durs[bi]
        cum_in_beat = 0.0
        for sn in scenes_by_beat[beat]:
            raw_d = real_dur_of[sn]
            remaining = final_dur - cum_in_beat
            if remaining <= 0:
                break
            visible_d = min(raw_d, remaining)
            if visible_d > 0.05:
                visible.append((sn, cum_beat_offset + cum_in_beat, visible_d))
            cum_in_beat += raw_d
        cum_beat_offset += final_dur

    # Đề xuất SFX cho từng cảnh SONG SONG (cùng bệnh + cùng cách sửa như sinh
    # prompt cảnh, xem storyboard.MAX_CONCURRENT_SCENE_PROMPT_CALLS) — với
    # ~37 cảnh, hỏi Claude tuần tự từng cảnh một (20-60s/lượt qua CLI) có
    # thể mất hơn 20 phút chỉ để chọn SFX. suggest_sfx_layers() tự nuốt lỗi
    # và trả về [] khi thất bại (xem docstring của nó trong llm.py) nên
    # không cần logic báo lỗi sớm — 1 cảnh lỗi chỉ thành cảnh không có SFX.
    raw_layers_of: dict[int, list[dict]] = {}
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_SFX_SUGGEST_CALLS) as executor:
        future_to_sn = {executor.submit(suggest_sfx_layers, prompt_of[sn]): sn for sn, _, _ in visible}
        for future, sn in future_to_sn.items():
            raw_layers_of[sn] = future.result()

    plans: list[ScenePlan] = []
    for sn, abs_start, visible_d in visible:
        layers = [
            SfxLayer(
                query_vi=str(rl.get("query_vi", "")).strip(),
                gain_db=float(rl.get("gain_db", -8.0)),
                start_offset=float(rl.get("start_offset", 0.0) or 0.0),
                duration=(float(rl["duration"]) if rl.get("duration") is not None else None),
                allow_birds=bool(rl.get("allow_birds", False)),
            )
            for rl in raw_layers_of[sn]
            if rl.get("query_vi")
        ]
        plans.append(ScenePlan(scene_n=sn, start_sec=abs_start, duration_sec=visible_d, layers=layers))

    sfx_index = build_sfx_index()
    out_path = workdir / "final_with_sfx.mp4"
    apply_step13_sfx(
        final_path, plans, out_path, workdir / "sfx", index=sfx_index,
        narration_volume_multiplier=job.narration_volume, sfx_boost_db=job.sfx_volume_db,
    )
    return out_path


def _add_title_card(
    job: ProductionJob,
    final_path: Path,
    beat_order: list[str],
    beat_narration_text: dict[str, str],
    format_: str,
    workdir: Path,
    include_poster: bool = True,
) -> tuple[Path, VideoMetadata | None]:
    """Bước 12: nhờ Claude sinh tiêu đề/phụ đề/mô tả/CTA từ toàn văn kịch
    bản (ghép lại từ các đoạn theo đúng thứ tự, ĐÚNG ngôn ngữ đang dựng).
    Bước 9: `include_poster=False` thì KHÔNG ghép poster mở đầu vào video
    (người dùng chọn "không có poster") — vẫn sinh tiêu đề/mô tả/CTA để
    dùng cho SEO/đăng bài (Bước 12), chỉ bỏ qua việc ghép ảnh vào đầu clip.
    Lỗi ở bước này (Claude chưa cấu hình, ffmpeg lỗi...) KHÔNG được làm
    hỏng cả job — video đã có SFX vẫn là kết quả hợp lệ, chỉ là thiếu
    tiêu đề. Mục 8, phần 3: sau khi vẽ xong poster, OCR lại để phát hiện
    chữ lem nhem/lỗi (error_checker.check_poster_text) — ghi cảnh báo vào
    job.quality_warnings, KHÔNG chặn việc ghép poster dù OCR lỗi."""
    full_script = "\n".join(beat_narration_text.get(b, "") for b in beat_order if beat_narration_text.get(b))
    if not full_script.strip():
        return final_path, None
    try:
        metadata = generate_metadata(full_script)
    except Exception as exc:  # noqa: BLE001 - thiếu tiêu đề không nên làm hỏng cả video đã dựng xong
        # LỖI THẬT đã gặp (2026-09): call LLM sinh tiêu đề/poster lỗi (hết
        # hạn mức CLI, mất mạng...) bị `except Exception: return final_path,
        # None` NUỐT HOÀN TOÀN — video vẫn ra thành công KHÔNG có poster,
        # người dùng đã chọn "Có poster" mà không hề biết vì sao thiếu, và
        # không có cách nào tra lại sau đó (báo lỗi thật: video Hannibal
        # Vượt Alps). Giờ PHẢI ghi rõ lý do vào job.quality_warnings (Mục 8)
        # để người dùng thấy ngay trên banner cảnh báo, dù vẫn không chặn
        # video đã dựng xong.
        job.quality_warnings.append(f"Không sinh được tiêu đề/poster mở đầu (Bước 12): {exc}")
        return final_path, None
    if not metadata.titles:
        job.quality_warnings.append(
            "Không ghép được poster mở đầu: LLM không trả về tiêu đề nào (Bước 12)."
        )
        return final_path, None
    if not include_poster:
        return final_path, metadata
    # Poster mở đầu chỉ in được 1 tiêu đề — dùng phương án đầu trong 10
    # tiêu đề Claude sinh ra; 9 cái còn lại (+ mô tả/CTA/thumbnail) vẫn
    # trả về nguyên trong `metadata` để người dùng tự chọn/copy sau.
    try:
        title_dir = workdir / "title_card"
        image_path = title_dir / "title.png"
        generate_title_card_image(
            metadata.titles[0], image_path, format_=format_, subtitle_text=metadata.subtitle or None
        )
        try:
            poster_warnings = error_checker.check_poster_text(image_path, metadata.titles[0], metadata.subtitle or "")
            job.quality_warnings.extend(poster_warnings)
        except Exception as exc:  # noqa: BLE001 - cảnh báo thêm, không được chặn việc ghép poster
            job.quality_warnings.append(f"Không chạy được kiểm tra chữ trên poster (Mục 8): {exc}")
        clip_path = title_dir / "title_clip.mp4"
        image_to_title_clip(image_path, clip_path, TITLE_CARD_DURATION_SEC, format_=format_)
        out_path = workdir / "final_with_title.mp4"
        concat_scenes([clip_path, final_path], out_path)
        return out_path, metadata
    except Exception as exc:  # noqa: BLE001 - ghép poster lỗi không nên làm hỏng cả video đã dựng xong
        job.quality_warnings.append(f"Ghép poster mở đầu vào video thất bại (Bước 9): {exc}")
        return final_path, metadata
