"""Test đầu-cuối cho Bước 9+10+13+12 nối liền (production_pipeline.py). Giả
lập 3 phần phụ thuộc ngoài không chạy được/không nên chạy thật trong môi
trường test: Google Flow (cần trình duyệt thật đã đăng nhập), Claude
suggest_sfx_layers + generate_metadata (cần cấu hình AI, giả lập cho nhanh
& xác định được kết quả). Phần còn lại (edge-tts, ffmpeg, tải hiệu ứng từ
tiengdong.com) chạy THẬT — đúng tinh thần các test khác trong dự án."""
from __future__ import annotations

import time
from pathlib import Path

from app.services import production_pipeline as pipeline
from app.services.quality_review import VideoMetadata
from app.services.video_builder import build_scene


def _fake_generate_video_with_retry(prompt: str, output_dir: Path, **kwargs):
    """Giả lập Google Flow: dựng 1 clip placeholder thật (ffmpeg) thay vì gọi
    trình duyệt — đủ để các bước dựng video/SFX phía sau xử lý như file thật."""
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "fake_flow_clip.mp4"
    result = build_scene(
        audio_path=_silent_audio(output_dir),
        out_path=out_path,
        video_path=None,
        format_="long",
    )
    return result.video_path


_SILENT_CACHE: dict[Path, Path] = {}


def _silent_audio(output_dir: Path) -> Path:
    """1 file audio ngắn dùng chung để build_scene() có input hợp lệ — nội
    dung không quan trọng vì đây chỉ là clip NỀN giả lập Flow, giọng đọc
    thật của video sẽ được ghi đè ở bước dựng đoạn (build_beat_scenes)."""
    import asyncio

    from app.services.video_builder import generate_narration

    key = output_dir.parent
    if key not in _SILENT_CACHE:
        p = key / "_silent_for_fake_flow.mp3"
        asyncio.run(generate_narration("placeholder.", "vi-VN", p))
        _SILENT_CACHE[key] = p
    return _SILENT_CACHE[key]


def _fake_suggest_sfx_layers(prompt_en: str) -> list[dict]:
    return [{"query_vi": "tiếng gió thổi nhẹ", "gain_db": -10.0, "start_offset": 0.0, "duration": None, "allow_birds": False}]


def _fake_generate_metadata(script_text: str) -> VideoMetadata:
    return VideoMetadata(
        titles=["Video Kiem Tra", "Video Kiem Tra 2"], subtitle="Ha Noi, 2026",
        descriptions=["Mo ta thu."], cta_texts=["Theo doi ngay!"], thumbnail_texts=["Kiem tra"],
    )


def _make_scenes_and_beats():
    scene_prompts = [
        {"scene_n": 1, "prompt": "Scene one, calm village morning."},
        {"scene_n": 2, "prompt": "Scene two, calm village evening."},
        {"scene_n": 3, "prompt": "Scene three, army marching."},
    ]
    beat_of_scene = {1: "HOOK", 2: "HOOK", 3: "VẤN ĐỀ"}
    beat_order = ["HOOK", "VẤN ĐỀ"]
    beat_narration_text = {
        "HOOK": "Đây là đoạn mở đầu của video kiểm tra.",
        "VẤN ĐỀ": "Đây là đoạn vấn đề của video kiểm tra.",
    }
    return scene_prompts, beat_of_scene, beat_order, beat_narration_text


def _wait_for_job(job, timeout=120):
    deadline = time.time() + timeout
    while job.status not in ("done", "failed") and time.time() < deadline:
        time.sleep(0.5)


def _wait_until(condition, timeout=15, interval=0.05):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if condition():
            return True
        time.sleep(interval)
    return False


def test_full_pipeline_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline.flow, "generate_video_with_retry", _fake_generate_video_with_retry)
    monkeypatch.setattr(pipeline, "suggest_sfx_layers", _fake_suggest_sfx_layers)
    monkeypatch.setattr(pipeline, "generate_metadata", _fake_generate_metadata)

    scene_prompts, beat_of_scene, beat_order, beat_narration_text = _make_scenes_and_beats()

    job_id = pipeline.start_job(
        scene_prompts=scene_prompts,
        beat_of_scene=beat_of_scene,
        beat_order=beat_order,
        beat_narration_text=beat_narration_text,
        source_language_code="vi-VN",
        language_codes=["vi-VN"],
        language_names={"vi-VN": "Tiếng Việt"},
        format_="long",
        workdir=tmp_path / "job",
    )

    job = pipeline.get_job(job_id)
    assert job is not None
    _wait_for_job(job)

    assert job.status == "done", f"Job thất bại: {job.error}"
    lang = job.languages["vi-VN"]
    assert lang.status == "done", f"Ngôn ngữ lỗi: {lang.error}"
    final_path = Path(lang.final_video_path)
    assert final_path.exists()
    assert final_path.stat().st_size > 0
    assert all(s.status == "done" for s in job.scenes.values())
    assert lang.metadata is not None
    assert lang.metadata.titles[0] == "Video Kiem Tra"
    assert "final_with_title" in final_path.name


def test_review_mode_pauses_after_each_scene_and_mode_switch_takes_effect_live(tmp_path, monkeypatch):
    """Bước 9, chế độ "review": job phải DỪNG LẠI sau mỗi cảnh tạo xong,
    chờ approve_scene() mới sang cảnh tiếp. Đổi sang "auto" NGAY LÚC ĐANG
    dừng chờ duyệt phải cho chạy tiếp luôn tới hết — đúng kịch bản người
    dùng mô tả: đổi qua đổi lại chế độ giữa chừng, không cần khởi động lại
    job."""
    monkeypatch.setattr(pipeline.flow, "generate_video_with_retry", _fake_generate_video_with_retry)
    monkeypatch.setattr(pipeline, "suggest_sfx_layers", _fake_suggest_sfx_layers)
    monkeypatch.setattr(pipeline, "generate_metadata", _fake_generate_metadata)

    scene_prompts, beat_of_scene, beat_order, beat_narration_text = _make_scenes_and_beats()
    job_id = pipeline.start_job(
        scene_prompts=scene_prompts,
        beat_of_scene=beat_of_scene,
        beat_order=beat_order,
        beat_narration_text=beat_narration_text,
        source_language_code="vi-VN",
        language_codes=["vi-VN"],
        language_names={"vi-VN": "Tiếng Việt"},
        format_="long",
        workdir=tmp_path / "job",
        run_mode="review",
    )
    job = pipeline.get_job(job_id)
    assert job is not None
    assert job.run_mode == "review"

    assert _wait_until(lambda: job.awaiting_review_scene == 1), "Phải dừng chờ duyệt cảnh 1"
    assert job.scenes[1].status == "done"
    assert job.scenes[2].status == "queued", "Chưa duyệt cảnh 1 thì cảnh 2 chưa được tạo"

    pipeline.approve_scene(job_id, 1)
    assert _wait_until(lambda: job.awaiting_review_scene == 2), "Phải dừng chờ duyệt cảnh 2"
    assert job.scenes[2].status == "done"
    assert job.scenes[3].status == "queued"

    # Đổi sang "auto" ngay lúc đang dừng chờ duyệt cảnh 2 -> chạy tiếp luôn
    # tới hết, không cần bấm duyệt cảnh 2 nữa.
    pipeline.set_run_mode(job_id, "auto")
    _wait_for_job(job)
    assert job.status == "done", f"Job thất bại: {job.error}"
    assert all(s.status == "done" for s in job.scenes.values())
    assert job.awaiting_review_scene is None


def test_review_mode_retry_regenerates_same_scene(tmp_path, monkeypatch):
    """action="retry": job phải tạo LẠI đúng cảnh đang dừng chờ (không sang
    cảnh kế), rồi vẫn dừng chờ duyệt cảnh đó lần nữa."""
    call_count_by_scene: dict[int, int] = {}

    def _counting_fake_flow(prompt: str, output_dir: Path, **kwargs):
        sn = int(output_dir.name.split("_")[1][:2])
        call_count_by_scene[sn] = call_count_by_scene.get(sn, 0) + 1
        return _fake_generate_video_with_retry(prompt, output_dir, **kwargs)

    monkeypatch.setattr(pipeline.flow, "generate_video_with_retry", _counting_fake_flow)
    monkeypatch.setattr(pipeline, "suggest_sfx_layers", _fake_suggest_sfx_layers)
    monkeypatch.setattr(pipeline, "generate_metadata", _fake_generate_metadata)

    scene_prompts, beat_of_scene, beat_order, beat_narration_text = _make_scenes_and_beats()
    job_id = pipeline.start_job(
        scene_prompts=scene_prompts, beat_of_scene=beat_of_scene, beat_order=beat_order,
        beat_narration_text=beat_narration_text, source_language_code="vi-VN",
        language_codes=["vi-VN"], language_names={"vi-VN": "Tiếng Việt"}, format_="long",
        workdir=tmp_path / "job", run_mode="review",
    )
    job = pipeline.get_job(job_id)
    assert _wait_until(lambda: job.awaiting_review_scene == 1)
    assert call_count_by_scene.get(1) == 1

    pipeline.approve_scene(job_id, 1, action="retry")
    assert _wait_until(lambda: call_count_by_scene.get(1) == 2), "Phải gọi lại Flow cho đúng cảnh 1"
    assert _wait_until(lambda: job.awaiting_review_scene == 1), "Vẫn dừng chờ duyệt lại đúng cảnh 1"
    assert job.scenes[2].status == "queued", "Chưa được sang cảnh 2 trong lúc đang tạo lại cảnh 1"

    pipeline.approve_scene(job_id, 1, action="approve")
    assert _wait_until(lambda: job.awaiting_review_scene == 2)
    pipeline.set_run_mode(job_id, "auto")
    _wait_for_job(job)
    assert job.status == "done", f"Job thất bại: {job.error}"


def test_review_mode_skip_excludes_scene_from_final_video(tmp_path, monkeypatch):
    """action="skip": cảnh bị đánh dấu "skipped", không nằm trong video cuối,
    và job vẫn tiếp tục sang cảnh kế tiếp."""
    monkeypatch.setattr(pipeline.flow, "generate_video_with_retry", _fake_generate_video_with_retry)
    monkeypatch.setattr(pipeline, "suggest_sfx_layers", _fake_suggest_sfx_layers)
    monkeypatch.setattr(pipeline, "generate_metadata", _fake_generate_metadata)

    scene_prompts, beat_of_scene, beat_order, beat_narration_text = _make_scenes_and_beats()
    job_id = pipeline.start_job(
        scene_prompts=scene_prompts, beat_of_scene=beat_of_scene, beat_order=beat_order,
        beat_narration_text=beat_narration_text, source_language_code="vi-VN",
        language_codes=["vi-VN"], language_names={"vi-VN": "Tiếng Việt"}, format_="long",
        workdir=tmp_path / "job", run_mode="review",
    )
    job = pipeline.get_job(job_id)
    assert _wait_until(lambda: job.awaiting_review_scene == 1)

    pipeline.approve_scene(job_id, 1, action="skip")
    assert _wait_until(lambda: job.awaiting_review_scene == 2), "Phải sang thẳng cảnh 2 sau khi bỏ qua cảnh 1"
    assert job.scenes[1].status == "skipped"

    pipeline.set_run_mode(job_id, "auto")
    _wait_for_job(job)
    assert job.status == "done", f"Job thất bại: {job.error}"
    assert job.scenes[1].status == "skipped"
    assert job.scenes[2].status == "done"
    assert job.scenes[3].status == "done"


def test_restore_scene_with_existing_video_is_instant(tmp_path, monkeypatch):
    """restore_scene(): cảnh bị "Bỏ qua" SAU KHI đã tạo thành công (video_path
    vẫn còn nguyên, skip không xoá) phải khôi phục ngay lập tức, không gọi
    lại Flow — đúng người dùng "đổi ý" sau khi xem trước, không phải lỗi."""
    call_count_by_scene: dict[int, int] = {}

    def _counting_fake_flow(prompt: str, output_dir: Path, **kwargs):
        sn = int(output_dir.name.split("_")[1][:2])
        call_count_by_scene[sn] = call_count_by_scene.get(sn, 0) + 1
        return _fake_generate_video_with_retry(prompt, output_dir, **kwargs)

    monkeypatch.setattr(pipeline.flow, "generate_video_with_retry", _counting_fake_flow)
    monkeypatch.setattr(pipeline, "suggest_sfx_layers", _fake_suggest_sfx_layers)
    monkeypatch.setattr(pipeline, "generate_metadata", _fake_generate_metadata)

    scene_prompts, beat_of_scene, beat_order, beat_narration_text = _make_scenes_and_beats()
    job_id = pipeline.start_job(
        scene_prompts=scene_prompts, beat_of_scene=beat_of_scene, beat_order=beat_order,
        beat_narration_text=beat_narration_text, source_language_code="vi-VN",
        language_codes=["vi-VN"], language_names={"vi-VN": "Tiếng Việt"}, format_="long",
        workdir=tmp_path / "job", run_mode="review",
    )
    job = pipeline.get_job(job_id)
    assert _wait_until(lambda: job.awaiting_review_scene == 1)
    assert job.scenes[1].status == "done"
    video_path_before_skip = job.scenes[1].video_path

    pipeline.approve_scene(job_id, 1, action="skip")
    assert _wait_until(lambda: job.awaiting_review_scene == 2)
    assert job.scenes[1].status == "skipped"
    assert job.scenes[1].video_path == video_path_before_skip, "skip không được xoá video cũ"

    restored = pipeline.restore_scene(job_id, 1)
    assert restored.scenes[1].status == "done"
    assert call_count_by_scene.get(1) == 1, "khôi phục cảnh còn video cũ không được gọi lại Flow"

    pipeline.set_run_mode(job_id, "auto")
    _wait_for_job(job)
    assert job.status == "done", f"Job thất bại: {job.error}"
    assert job.scenes[1].status == "done", "cảnh khôi phục phải nằm trong video cuối"


def test_restore_scene_without_video_regenerates(tmp_path, monkeypatch):
    """restore_scene(): cảnh bị lỗi rồi mới "Bỏ qua" (chưa từng có video)
    phải tạo lại từ đầu khi khôi phục, chạy nền không chặn request."""
    call_count_by_scene: dict[int, int] = {}

    def _fake_flow_fail_scene1_once(prompt: str, output_dir: Path, **kwargs):
        sn = int(output_dir.name.split("_")[1][:2])
        call_count_by_scene[sn] = call_count_by_scene.get(sn, 0) + 1
        if sn == 1 and call_count_by_scene[sn] == 1:
            raise RuntimeError("Giả lập Flow lỗi lần đầu cho cảnh 1")
        return _fake_generate_video_with_retry(prompt, output_dir, **kwargs)

    monkeypatch.setattr(pipeline.flow, "generate_video_with_retry", _fake_flow_fail_scene1_once)
    monkeypatch.setattr(pipeline, "suggest_sfx_layers", _fake_suggest_sfx_layers)
    monkeypatch.setattr(pipeline, "generate_metadata", _fake_generate_metadata)

    scene_prompts, beat_of_scene, beat_order, beat_narration_text = _make_scenes_and_beats()
    job_id = pipeline.start_job(
        scene_prompts=scene_prompts, beat_of_scene=beat_of_scene, beat_order=beat_order,
        beat_narration_text=beat_narration_text, source_language_code="vi-VN",
        language_codes=["vi-VN"], language_names={"vi-VN": "Tiếng Việt"}, format_="long",
        workdir=tmp_path / "job", run_mode="review",
    )
    job = pipeline.get_job(job_id)
    assert _wait_until(lambda: job.awaiting_review_scene == 1)
    assert job.scenes[1].status == "failed"
    assert job.scenes[1].video_path is None

    pipeline.approve_scene(job_id, 1, action="skip")
    assert _wait_until(lambda: job.awaiting_review_scene == 2)
    assert job.scenes[1].status == "skipped"

    pipeline.restore_scene(job_id, 1)
    assert job.scenes[1].status == "generating", "phải chuyển sang 'generating' ngay khi bắt đầu tạo lại"
    assert _wait_until(lambda: job.scenes[1].status == "done", timeout=30), f"Khôi phục thất bại: {job.scenes[1].error}"
    assert call_count_by_scene.get(1) == 2, "phải gọi lại Flow đúng 1 lần khi khôi phục"

    pipeline.set_run_mode(job_id, "auto")
    _wait_for_job(job)
    assert job.status == "done", f"Job thất bại: {job.error}"
    assert job.scenes[1].status == "done"


def test_restore_scene_rejects_after_generating_scenes_phase(tmp_path, monkeypatch):
    """restore_scene(): job đã sang bước dựng video (beat clip đã ghép xong)
    thì không cho khôi phục nữa — cần chạy job sản xuất mới."""
    monkeypatch.setattr(pipeline.flow, "generate_video_with_retry", _fake_generate_video_with_retry)
    monkeypatch.setattr(pipeline, "suggest_sfx_layers", _fake_suggest_sfx_layers)
    monkeypatch.setattr(pipeline, "generate_metadata", _fake_generate_metadata)

    scene_prompts, beat_of_scene, beat_order, beat_narration_text = _make_scenes_and_beats()
    job_id = pipeline.start_job(
        scene_prompts=scene_prompts, beat_of_scene=beat_of_scene, beat_order=beat_order,
        beat_narration_text=beat_narration_text, source_language_code="vi-VN",
        language_codes=["vi-VN"], language_names={"vi-VN": "Tiếng Việt"}, format_="long",
        workdir=tmp_path / "job", run_mode="review",
    )
    job = pipeline.get_job(job_id)
    assert _wait_until(lambda: job.awaiting_review_scene == 1)
    pipeline.approve_scene(job_id, 1, action="skip")
    assert _wait_until(lambda: job.awaiting_review_scene == 2)
    pipeline.set_run_mode(job_id, "auto")
    _wait_for_job(job)
    assert job.status == "done", f"Job thất bại: {job.error}"

    try:
        pipeline.restore_scene(job_id, 1)
        assert False, "phải ném ValueError khi job đã qua bước tạo cảnh"
    except ValueError:
        pass
    assert job.scenes[1].status == "skipped", "không được đụng vào trạng thái cảnh khi từ chối khôi phục"


def test_resolve_failed_scene_retry_regenerates_scene(tmp_path, monkeypatch):
    """resolve_failed_scene(job_id, n, "retry"): cảnh "Lỗi" mà job đã chạy
    qua (không dừng lại hỏi như review) tạo lại thành công khi người dùng
    chủ động bấm."""
    call_count_by_scene: dict[int, int] = {}

    def _fake_flow_fail_scene1_once(prompt: str, output_dir: Path, **kwargs):
        sn = int(output_dir.name.split("_")[1][:2])
        call_count_by_scene[sn] = call_count_by_scene.get(sn, 0) + 1
        if sn == 1 and call_count_by_scene[sn] == 1:
            raise RuntimeError("Giả lập Flow lỗi lần đầu cho cảnh 1")
        return _fake_generate_video_with_retry(prompt, output_dir, **kwargs)

    monkeypatch.setattr(pipeline.flow, "generate_video_with_retry", _fake_flow_fail_scene1_once)
    monkeypatch.setattr(pipeline, "suggest_sfx_layers", _fake_suggest_sfx_layers)
    monkeypatch.setattr(pipeline, "generate_metadata", _fake_generate_metadata)

    scene_prompts, beat_of_scene, beat_order, beat_narration_text = _make_scenes_and_beats()
    job_id = pipeline.start_job(
        scene_prompts=scene_prompts, beat_of_scene=beat_of_scene, beat_order=beat_order,
        beat_narration_text=beat_narration_text, source_language_code="vi-VN",
        language_codes=["vi-VN"], language_names={"vi-VN": "Tiếng Việt"}, format_="long",
        workdir=tmp_path / "job", run_mode="review",
    )
    job = pipeline.get_job(job_id)
    assert _wait_until(lambda: job.awaiting_review_scene == 1)
    assert job.scenes[1].status == "failed"

    pipeline.resolve_failed_scene(job_id, 1, "retry")
    assert job.scenes[1].status == "generating"
    assert _wait_until(lambda: job.scenes[1].status == "done", timeout=30), f"Tạo lại thất bại: {job.scenes[1].error}"
    assert call_count_by_scene.get(1) == 2

    pipeline.set_run_mode(job_id, "auto")
    _wait_for_job(job)
    assert job.status == "done", f"Job thất bại: {job.error}"
    assert job.scenes[1].status == "done"


def test_resolve_failed_scene_skip_marks_skipped(tmp_path, monkeypatch):
    def _fake_flow_fail_scene1(prompt: str, output_dir: Path, **kwargs):
        sn = int(output_dir.name.split("_")[1][:2])
        if sn == 1:
            raise RuntimeError("Giả lập Flow lỗi cho cảnh 1")
        return _fake_generate_video_with_retry(prompt, output_dir, **kwargs)

    monkeypatch.setattr(pipeline.flow, "generate_video_with_retry", _fake_flow_fail_scene1)
    monkeypatch.setattr(pipeline, "suggest_sfx_layers", _fake_suggest_sfx_layers)
    monkeypatch.setattr(pipeline, "generate_metadata", _fake_generate_metadata)

    scene_prompts, beat_of_scene, beat_order, beat_narration_text = _make_scenes_and_beats()
    job_id = pipeline.start_job(
        scene_prompts=scene_prompts, beat_of_scene=beat_of_scene, beat_order=beat_order,
        beat_narration_text=beat_narration_text, source_language_code="vi-VN",
        language_codes=["vi-VN"], language_names={"vi-VN": "Tiếng Việt"}, format_="long",
        workdir=tmp_path / "job", run_mode="review",
    )
    job = pipeline.get_job(job_id)
    assert _wait_until(lambda: job.awaiting_review_scene == 1)
    assert job.scenes[1].status == "failed"

    pipeline.resolve_failed_scene(job_id, 1, "skip")
    assert job.scenes[1].status == "skipped"

    pipeline.set_run_mode(job_id, "auto")
    _wait_for_job(job)
    assert job.status == "done", f"Job thất bại: {job.error}"
    assert job.scenes[1].status == "skipped"


def test_resolve_failed_scene_delete_removes_leftover_files(tmp_path, monkeypatch):
    """action="delete": phải dọn sạch thư mục tải về dở dang của đúng cảnh
    đó trên đĩa, không đụng tới cảnh khác."""
    def _fake_flow_fail_with_leftover(prompt: str, output_dir: Path, **kwargs):
        sn = int(output_dir.name.split("_")[1][:2])
        if sn == 1:
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "partial.mp4").write_bytes(b"junk")
            raise RuntimeError("Giả lập lỗi sau khi tải dở dang")
        return _fake_generate_video_with_retry(prompt, output_dir, **kwargs)

    monkeypatch.setattr(pipeline.flow, "generate_video_with_retry", _fake_flow_fail_with_leftover)
    monkeypatch.setattr(pipeline, "suggest_sfx_layers", _fake_suggest_sfx_layers)
    monkeypatch.setattr(pipeline, "generate_metadata", _fake_generate_metadata)

    scene_prompts, beat_of_scene, beat_order, beat_narration_text = _make_scenes_and_beats()
    workdir = tmp_path / "job"
    job_id = pipeline.start_job(
        scene_prompts=scene_prompts, beat_of_scene=beat_of_scene, beat_order=beat_order,
        beat_narration_text=beat_narration_text, source_language_code="vi-VN",
        language_codes=["vi-VN"], language_names={"vi-VN": "Tiếng Việt"}, format_="long",
        workdir=workdir, run_mode="review",
    )
    job = pipeline.get_job(job_id)
    assert _wait_until(lambda: job.awaiting_review_scene == 1)
    assert job.scenes[1].status == "failed"
    leftover = workdir / "downloads" / "scene_01" / "partial.mp4"
    assert leftover.exists(), "test phải tạo được file dở dang trước khi kiểm tra xoá"

    pipeline.resolve_failed_scene(job_id, 1, "delete")
    assert job.scenes[1].status == "skipped"
    assert not leftover.exists(), "phải xoá file dở dang trên đĩa"
    assert not (workdir / "downloads" / "scene_01").exists()

    pipeline.set_run_mode(job_id, "auto")
    _wait_for_job(job)
    assert job.status == "done", f"Job thất bại: {job.error}"


def test_resolve_failed_scene_rejects_invalid_action(tmp_path, monkeypatch):
    job = pipeline.ProductionJob(job_id="job-failed-invalid", status="generating_scenes")
    job.scenes[1] = pipeline.SceneProgress(scene_n=1, status="failed")
    pipeline._JOBS["job-failed-invalid"] = job
    try:
        pipeline.resolve_failed_scene("job-failed-invalid", 1, "khong-hop-le")
        assert False, "phải ném ValueError khi action không hợp lệ"
    except ValueError:
        pass
    assert job.scenes[1].status == "failed"


def test_resolve_failed_scene_rejects_after_generating_scenes_phase(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline.flow, "generate_video_with_retry", _fake_generate_video_with_retry)
    monkeypatch.setattr(pipeline, "suggest_sfx_layers", _fake_suggest_sfx_layers)
    monkeypatch.setattr(pipeline, "generate_metadata", _fake_generate_metadata)

    scene_prompts, beat_of_scene, beat_order, beat_narration_text = _make_scenes_and_beats()
    job_id = pipeline.start_job(
        scene_prompts=scene_prompts, beat_of_scene=beat_of_scene, beat_order=beat_order,
        beat_narration_text=beat_narration_text, source_language_code="vi-VN",
        language_codes=["vi-VN"], language_names={"vi-VN": "Tiếng Việt"}, format_="long",
        workdir=tmp_path / "job",
    )
    job = pipeline.get_job(job_id)
    _wait_for_job(job)
    assert job.status == "done", f"Job thất bại: {job.error}"

    try:
        pipeline.resolve_failed_scene(job_id, 1, "retry")
        assert False, "phải ném ValueError khi job đã qua bước tạo cảnh"
    except ValueError:
        pass


def test_approve_scene_rejects_invalid_action(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline.flow, "generate_video_with_retry", _fake_generate_video_with_retry)
    monkeypatch.setattr(pipeline, "suggest_sfx_layers", _fake_suggest_sfx_layers)
    monkeypatch.setattr(pipeline, "generate_metadata", _fake_generate_metadata)
    scene_prompts, beat_of_scene, beat_order, beat_narration_text = _make_scenes_and_beats()
    job_id = pipeline.start_job(
        scene_prompts=scene_prompts, beat_of_scene=beat_of_scene, beat_order=beat_order,
        beat_narration_text=beat_narration_text, source_language_code="vi-VN",
        language_codes=["vi-VN"], language_names={"vi-VN": "Tiếng Việt"}, format_="long",
        workdir=tmp_path / "job", run_mode="review",
    )
    job = pipeline.get_job(job_id)
    assert _wait_until(lambda: job.awaiting_review_scene == 1)

    try:
        pipeline.approve_scene(job_id, 1, action="khong-hop-le")
        assert False, "phải ném ValueError khi action không hợp lệ"
    except ValueError:
        pass
    assert job.awaiting_review_scene == 1

    pipeline.set_run_mode(job_id, "auto")  # dọn cho job chạy hết, tránh treo thread nền
    _wait_for_job(job)


def test_approve_scene_rejects_wrong_scene_number(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline.flow, "generate_video_with_retry", _fake_generate_video_with_retry)
    monkeypatch.setattr(pipeline, "suggest_sfx_layers", _fake_suggest_sfx_layers)
    monkeypatch.setattr(pipeline, "generate_metadata", _fake_generate_metadata)
    scene_prompts, beat_of_scene, beat_order, beat_narration_text = _make_scenes_and_beats()
    job_id = pipeline.start_job(
        scene_prompts=scene_prompts, beat_of_scene=beat_of_scene, beat_order=beat_order,
        beat_narration_text=beat_narration_text, source_language_code="vi-VN",
        language_codes=["vi-VN"], language_names={"vi-VN": "Tiếng Việt"}, format_="long",
        workdir=tmp_path / "job", run_mode="review",
    )
    job = pipeline.get_job(job_id)
    assert _wait_until(lambda: job.awaiting_review_scene == 1)

    try:
        pipeline.approve_scene(job_id, 99)
        assert False, "phải ném ValueError khi duyệt sai số cảnh"
    except ValueError:
        pass
    assert job.awaiting_review_scene == 1, "Duyệt sai cảnh không được ảnh hưởng job đang dừng đúng chỗ"

    pipeline.set_run_mode(job_id, "auto")  # dọn cho job chạy hết, tránh treo thread nền
    _wait_for_job(job)


def test_pipeline_dispatches_scene_type_to_correct_renderer(tmp_path, monkeypatch):
    """Bước 8: cảnh motion_text KHÔNG được gọi Flow (thuần ffmpeg), cảnh
    ai_video vẫn gọi Flow như trước — xác nhận qua production_pipeline thật
    (không mock scene_renderers, chỉ mock Flow bên dưới)."""
    flow_calls = []

    def fake_generate_video_with_retry(prompt, output_dir, **kwargs):
        flow_calls.append(prompt)
        return _fake_generate_video_with_retry(prompt, output_dir, **kwargs)

    monkeypatch.setattr(pipeline.flow, "generate_video_with_retry", fake_generate_video_with_retry)
    monkeypatch.setattr(pipeline, "suggest_sfx_layers", _fake_suggest_sfx_layers)
    monkeypatch.setattr(pipeline, "generate_metadata", _fake_generate_metadata)

    scene_prompts = [
        {"scene_n": 1, "prompt": "Scene one, calm village morning.", "scene_type": "ai_video", "duration_sec": 8},
        {"scene_n": 2, "prompt": "BREAKING POINT", "scene_type": "motion_text", "duration_sec": 3},
    ]
    beat_of_scene = {1: "HOOK", 2: "HOOK"}
    beat_order = ["HOOK"]
    beat_narration_text = {"HOOK": "Đây là đoạn mở đầu của video kiểm tra."}

    job_id = pipeline.start_job(
        scene_prompts=scene_prompts, beat_of_scene=beat_of_scene, beat_order=beat_order,
        beat_narration_text=beat_narration_text, source_language_code="vi-VN",
        language_codes=["vi-VN"], language_names={"vi-VN": "Tiếng Việt"}, format_="long",
        workdir=tmp_path / "job",
    )
    job = pipeline.get_job(job_id)
    _wait_for_job(job)

    assert job.status == "done", f"Job thất bại: {job.error}"
    assert flow_calls == ["Scene one, calm village morning."], "motion_text không được gọi Flow"
    assert job.scenes[1].status == "done" and job.scenes[1].scene_type == "ai_video"
    assert job.scenes[2].status == "done" and job.scenes[2].scene_type == "motion_text"
    assert Path(job.scenes[2].video_path).exists()


def test_pipeline_populates_quality_warnings_when_characters_given(tmp_path, monkeypatch):
    """Mục 8: khi có Sổ Tay Nhân Vật, job phải chạy kiểm tra nhân vật đổi
    hình dạng và ghi cảnh báo vào job.quality_warnings — mock compute_embedding
    (không tải CLIP thật, xem tests/test_character_consistency.py cho test
    logic thuần) để test NHANH riêng phần NỐI DÂY vào pipeline."""
    import numpy as np

    from app.services import character_consistency

    monkeypatch.setattr(pipeline.flow, "generate_video_with_retry", _fake_generate_video_with_retry)
    monkeypatch.setattr(pipeline, "suggest_sfx_layers", _fake_suggest_sfx_layers)
    monkeypatch.setattr(pipeline, "generate_metadata", _fake_generate_metadata)

    # cảnh 1 và 2 (cả 2 đều nhắc "Gióng") có embedding LỆCH hẳn -> phải bị cảnh báo.
    fake_vectors = {1: np.array([1.0, 0.0]), 2: np.array([0.0, 1.0]), 3: np.array([0.9, 0.1])}
    monkeypatch.setattr(
        character_consistency, "compute_embedding",
        lambda image_path: fake_vectors[int(str(image_path).split("_")[-1].split(".")[0])],
    )

    scene_prompts = [
        {"scene_n": 1, "prompt": "Scene one.", "source_text": "Gióng đứng dậy."},
        {"scene_n": 2, "prompt": "Scene two.", "source_text": "Gióng khoác áo giáp sắt."},
        {"scene_n": 3, "prompt": "Scene three.", "source_text": "Trời đêm yên tĩnh."},
    ]
    beat_of_scene = {1: "HOOK", 2: "HOOK", 3: "VẤN ĐỀ"}
    beat_order = ["HOOK", "VẤN ĐỀ"]
    beat_narration_text = {
        "HOOK": "Đây là đoạn mở đầu của video kiểm tra.",
        "VẤN ĐỀ": "Đây là đoạn vấn đề của video kiểm tra.",
    }
    job_id = pipeline.start_job(
        scene_prompts=scene_prompts, beat_of_scene=beat_of_scene, beat_order=beat_order,
        beat_narration_text=beat_narration_text, source_language_code="vi-VN",
        language_codes=["vi-VN"], language_names={"vi-VN": "Tiếng Việt"}, format_="long",
        workdir=tmp_path / "job", characters=[{"name": "Gióng", "description": "áo giáp sắt"}],
    )
    job = pipeline.get_job(job_id)
    _wait_for_job(job)

    assert job.status == "done", f"Job thất bại: {job.error}"
    assert any("Gióng" in w and "1" in w and "2" in w for w in job.quality_warnings), job.quality_warnings


def test_pipeline_skips_consistency_check_when_no_characters(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline.flow, "generate_video_with_retry", _fake_generate_video_with_retry)
    monkeypatch.setattr(pipeline, "suggest_sfx_layers", _fake_suggest_sfx_layers)
    monkeypatch.setattr(pipeline, "generate_metadata", _fake_generate_metadata)
    scene_prompts, beat_of_scene, beat_order, beat_narration_text = _make_scenes_and_beats()
    job_id = pipeline.start_job(
        scene_prompts=scene_prompts, beat_of_scene=beat_of_scene, beat_order=beat_order,
        beat_narration_text=beat_narration_text, source_language_code="vi-VN",
        language_codes=["vi-VN"], language_names={"vi-VN": "Tiếng Việt"}, format_="long",
        workdir=tmp_path / "job",
    )
    job = pipeline.get_job(job_id)
    _wait_for_job(job)
    assert job.status == "done", f"Job thất bại: {job.error}"
    # Không truyền `characters` -> kiểm tra nhân vật đổi hình dạng phải được
    # BỎ QUA hoàn toàn (không có cảnh báo nào nhắc "nhân vật" trong đó).
    # Máy chạy test này có thể vẫn có cảnh báo KHÁC không liên quan (VD
    # thiếu Tesseract-OCR cho kiểm tra chữ poster) — không phải phạm vi test.
    assert not any("nhân vật" in w for w in job.quality_warnings), job.quality_warnings


def test_set_run_mode_rejects_unknown_job():
    try:
        pipeline.set_run_mode("khong-ton-tai-abc", "auto")
        assert False, "phải ném KeyError"
    except KeyError:
        pass


def test_start_job_rejects_invalid_run_mode(tmp_path):
    scene_prompts, beat_of_scene, beat_order, beat_narration_text = _make_scenes_and_beats()
    try:
        pipeline.start_job(
            scene_prompts=scene_prompts, beat_of_scene=beat_of_scene, beat_order=beat_order,
            beat_narration_text=beat_narration_text, source_language_code="vi-VN",
            language_codes=["vi-VN"], language_names={"vi-VN": "Tiếng Việt"}, format_="long",
            workdir=tmp_path / "job", run_mode="khong-hop-le",
        )
        assert False, "phải ném ValueError"
    except ValueError:
        pass


def test_multi_language_reuses_flow_scenes_and_translates(tmp_path, monkeypatch):
    """Xuất 2 ngôn ngữ trong 1 job: Google Flow chỉ được gọi ĐÚNG 1 LẦN cho
    mỗi cảnh (dùng chung, không tạo lại) — đúng tinh thần Bước 3 (tránh tốn
    credit lặp lại). Ngôn ngữ khác ngôn ngữ gốc phải được dịch qua
    `translate_text`."""
    flow_call_count = {"n": 0}

    def _counting_fake_flow(prompt, output_dir, **kwargs):
        flow_call_count["n"] += 1
        return _fake_generate_video_with_retry(prompt, output_dir, **kwargs)

    translated_calls = []

    def _fake_translate(text, target_language_name):
        translated_calls.append((text, target_language_name))
        return f"[{target_language_name}] {text}"

    monkeypatch.setattr(pipeline.flow, "generate_video_with_retry", _counting_fake_flow)
    monkeypatch.setattr(pipeline, "suggest_sfx_layers", _fake_suggest_sfx_layers)
    monkeypatch.setattr(pipeline, "generate_metadata", _fake_generate_metadata)
    monkeypatch.setattr(pipeline, "translate_text", _fake_translate)

    scene_prompts, beat_of_scene, beat_order, beat_narration_text = _make_scenes_and_beats()

    job_id = pipeline.start_job(
        scene_prompts=scene_prompts,
        beat_of_scene=beat_of_scene,
        beat_order=beat_order,
        beat_narration_text=beat_narration_text,
        source_language_code="vi-VN",
        language_codes=["vi-VN", "en-US"],
        language_names={"vi-VN": "Tiếng Việt", "en-US": "Tiếng Anh"},
        format_="long",
        workdir=tmp_path / "job",
    )
    job = pipeline.get_job(job_id)
    _wait_for_job(job)

    assert job.status == "done", f"Job thất bại: {job.error}"
    assert job.languages["vi-VN"].status == "done"
    assert job.languages["en-US"].status == "done", f"Lỗi: {job.languages['en-US'].error}"
    assert flow_call_count["n"] == len(scene_prompts), "Flow phải chỉ được gọi 1 lần/cảnh, dùng chung cho mọi ngôn ngữ"
    assert len(translated_calls) == len(beat_narration_text), "Chỉ ngôn ngữ khác gốc mới cần dịch"
    assert all(lang_name == "Tiếng Anh" for _, lang_name in translated_calls)
    vi_path = Path(job.languages["vi-VN"].final_video_path)
    en_path = Path(job.languages["en-US"].final_video_path)
    assert vi_path.exists() and en_path.exists()
    assert vi_path != en_path


def test_job_not_found_returns_none():
    assert pipeline.get_job("khong-ton-tai") is None


# --- Dịch lời dẫn + chọn SFX SONG SONG (2026-09-15): tuần tự từng cặp -----
# (ngôn ngữ, đoạn)/từng cảnh với backend CLI (mỗi lượt gọi 20-60s) có thể
# mất hàng chục phút — xem MAX_CONCURRENT_TRANSLATE_CALLS/
# MAX_CONCURRENT_SFX_SUGGEST_CALLS trong production_pipeline.py.
# ---------------------------------------------------------------------------

def test_translate_all_beats_preserves_mapping_despite_concurrent_completion(monkeypatch):
    """Nhiều cặp (ngôn ngữ, đoạn) dịch song song có thể hoàn thành không theo
    thứ tự gửi đi (đoạn lẻ giả lập chậm hơn đoạn chẵn) — kết quả trả về vẫn
    phải khớp ĐÚNG ngôn ngữ/đoạn tương ứng, không bị lẫn."""
    beat_narration_text = {f"BEAT_{i}": f"Nội dung gốc đoạn {i}." for i in range(1, 5)}
    language_codes = ["vi-VN", "en-US", "ru-RU"]
    language_names = {"vi-VN": "Tiếng Việt", "en-US": "Tiếng Anh", "ru-RU": "Tiếng Nga"}

    def fake_translate(text: str, target_language_name: str) -> str:
        beat_num = int(text.rsplit(" ", 1)[1].rstrip("."))
        time.sleep(0.05 if beat_num % 2 == 1 else 0.01)
        return f"[{target_language_name}] đoạn {beat_num}"

    monkeypatch.setattr(pipeline, "translate_text", fake_translate)
    result = pipeline._translate_all_beats(
        beat_narration_text, language_codes, source_language_code="vi-VN", language_names=language_names,
    )

    assert result["vi-VN"] == beat_narration_text, "Ngôn ngữ gốc không cần dịch, giữ nguyên văn"
    for lang in ("en-US", "ru-RU"):
        for i in range(1, 5):
            assert result[lang][f"BEAT_{i}"] == f"[{language_names[lang]}] đoạn {i}"


def test_translate_all_beats_skips_llm_call_when_no_extra_language(monkeypatch):
    """Chỉ có ngôn ngữ gốc trong job (VD người dùng chỉ xuất 1 thứ tiếng) —
    không được gọi translate_text lần nào, tránh tốn thời gian khởi tạo
    ThreadPoolExecutor cho việc không cần làm."""
    calls = []
    monkeypatch.setattr(pipeline, "translate_text", lambda *a: calls.append(a) or "khong dung toi")
    beat_narration_text = {"HOOK": "Xin chào."}
    result = pipeline._translate_all_beats(
        beat_narration_text, ["vi-VN"], source_language_code="vi-VN", language_names={"vi-VN": "Tiếng Việt"},
    )
    assert result == {"vi-VN": beat_narration_text}
    assert calls == []


def _make_job_for_sfx_test(n_scenes: int) -> tuple[pipeline.ProductionJob, list[dict], dict[int, str], list[str], list[Path]]:
    job = pipeline.ProductionJob(job_id="test-sfx-job")
    scene_prompts = []
    beat_of_scene = {}
    half = n_scenes // 2
    for sn in range(1, n_scenes + 1):
        job.scenes[sn] = pipeline.SceneProgress(scene_n=sn, status="done", video_path=f"scene_{sn}.mp4")
        scene_prompts.append({"scene_n": sn, "prompt": f"scene-{sn}"})
        beat_of_scene[sn] = "A" if sn <= half else "B"
    beat_order = ["A", "B"]
    scene_build_paths = [Path("beat_A.mp4"), Path("beat_B.mp4")]
    return job, scene_prompts, beat_of_scene, beat_order, scene_build_paths


def test_apply_sfx_preserves_scene_order_despite_concurrent_completion(monkeypatch, tmp_path):
    """suggest_sfx_layers() chạy song song cho nhiều cảnh cùng lúc (cảnh lẻ
    giả lập chậm hơn cảnh chẵn) — danh sách ScenePlan trả về vẫn phải ĐÚNG
    thứ tự scene_n như storyboard, không bị xáo trộn theo thứ tự hoàn
    thành thật của từng lượt gọi."""
    job, scene_prompts, beat_of_scene, beat_order, scene_build_paths = _make_job_for_sfx_test(8)

    def fake_probe_duration(path: Path) -> float:
        # Mỗi cảnh "dài" 2s; mỗi đoạn (beat) gồm 4 cảnh nên "dài" đủ 8s để
        # cả 4 cảnh đều hiển thị trọn vẹn trong video cuối.
        return 8.0 if Path(path).name.startswith("beat_") else 2.0

    def fake_suggest_sfx_layers(prompt_en: str) -> list[dict]:
        scene_num = int(prompt_en.rsplit("-", 1)[1])
        time.sleep(0.05 if scene_num % 2 == 1 else 0.01)
        return [{"query_vi": f"sfx-{scene_num}", "gain_db": -8.0, "start_offset": 0.0, "duration": None, "allow_birds": False}]

    captured_plans = {}

    def fake_apply_step13_sfx(final_video_path, scene_plans, out_path, workdir, **kwargs):
        captured_plans["plans"] = scene_plans
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"fake")
        return out_path

    monkeypatch.setattr(pipeline, "_probe_duration", fake_probe_duration)
    monkeypatch.setattr(pipeline, "suggest_sfx_layers", fake_suggest_sfx_layers)
    monkeypatch.setattr(pipeline, "build_sfx_index", lambda: [])
    monkeypatch.setattr(pipeline, "apply_step13_sfx", fake_apply_step13_sfx)

    pipeline._apply_sfx(
        job, Path("final.mp4"), scene_prompts, beat_of_scene, beat_order, scene_build_paths, tmp_path,
    )

    plans = captured_plans["plans"]
    assert [p.scene_n for p in plans] == list(range(1, 9))
    assert [p.layers[0].query_vi for p in plans] == [f"sfx-{i}" for i in range(1, 9)]
