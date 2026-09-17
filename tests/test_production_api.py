from fastapi.testclient import TestClient

from app.api import production as production_api
from app.main import app
from app.services import production_pipeline as pipeline

client = TestClient(app)


def test_get_unknown_job_returns_404():
    res = client.get("/api/production/khong-ton-tai")
    assert res.status_code == 404


def test_download_video_before_done_returns_409(monkeypatch):
    job = pipeline.ProductionJob(job_id="job1", status="building_languages")
    job.languages["vi-VN"] = pipeline.LanguageResult(language_code="vi-VN", status="building_video")
    monkeypatch.setitem(pipeline._JOBS, "job1", job)
    res = client.get("/api/production/job1/video?language_code=vi-VN")
    assert res.status_code == 409


def test_download_video_unknown_language_returns_404(monkeypatch):
    job = pipeline.ProductionJob(job_id="job2", status="done")
    job.languages["vi-VN"] = pipeline.LanguageResult(language_code="vi-VN", status="done")
    monkeypatch.setitem(pipeline._JOBS, "job2", job)
    res = client.get("/api/production/job2/video?language_code=fr-FR")
    assert res.status_code == 404


def test_start_rejects_scene_not_in_any_beat():
    payload = {
        "scenes": [{"scene_n": 1, "prompt": "a"}, {"scene_n": 2, "prompt": "b"}],
        "beats": [{"label": "beat_0", "narration_text": "x", "scene_ns": [1]}],
        "source_language_code": "vi-VN",
        "language_codes": ["vi-VN"],
        "format": "long",
    }
    res = client.post("/api/production/start", json=payload)
    assert res.status_code == 400
    assert "2" in res.json()["detail"]


def test_start_spawns_job_and_status_is_pollable(monkeypatch, tmp_path):
    calls = []

    def fake_start_job(**kwargs):
        calls.append(kwargs)
        job = pipeline.ProductionJob(job_id="fixed-job-id")
        pipeline._JOBS["fixed-job-id"] = job
        return job.job_id

    monkeypatch.setattr(production_api, "start_job", fake_start_job)

    payload = {
        "scenes": [{"scene_n": 1, "prompt": "a scene"}],
        "beats": [{"label": "beat_0", "narration_text": "lời dẫn", "scene_ns": [1]}],
        "source_language_code": "vi-VN",
        "language_codes": ["vi-VN", "en-US"],
        "format": "long",
    }
    res = client.post("/api/production/start", json=payload)
    assert res.status_code == 200
    job_id = res.json()["job_id"]
    assert calls[0]["beat_of_scene"] == {1: "beat_0"}
    assert calls[0]["language_codes"] == ["vi-VN", "en-US"]
    assert calls[0]["language_names"]["vi-VN"] == "Tiếng Việt"

    status_res = client.get(f"/api/production/{job_id}")
    assert status_res.status_code == 200
    body = status_res.json()
    assert body["status"] == "queued"
    assert body["run_mode"] == "auto"
    assert body["awaiting_review_scene"] is None
    assert calls[0]["run_mode"] == "auto"


def test_start_passes_through_review_run_mode(monkeypatch):
    def fake_start_job(**kwargs):
        job = pipeline.ProductionJob(job_id="job-review", run_mode=kwargs["run_mode"])
        pipeline._JOBS["job-review"] = job
        return job.job_id

    monkeypatch.setattr(production_api, "start_job", fake_start_job)
    payload = {
        "scenes": [{"scene_n": 1, "prompt": "a scene"}],
        "beats": [{"label": "beat_0", "narration_text": "lời dẫn", "scene_ns": [1]}],
        "source_language_code": "vi-VN",
        "language_codes": ["vi-VN"],
        "format": "long",
        "run_mode": "review",
    }
    res = client.post("/api/production/start", json=payload)
    assert res.status_code == 200
    assert client.get(f"/api/production/{res.json()['job_id']}").json()["run_mode"] == "review"


def test_start_rejects_invalid_run_mode():
    payload = {
        "scenes": [{"scene_n": 1, "prompt": "a"}],
        "beats": [{"label": "beat_0", "narration_text": "x", "scene_ns": [1]}],
        "source_language_code": "vi-VN",
        "language_codes": ["vi-VN"],
        "run_mode": "khong-hop-le",
    }
    res = client.post("/api/production/start", json=payload)
    assert res.status_code == 400


def test_set_mode_unknown_job_returns_404():
    res = client.post("/api/production/khong-ton-tai/mode", json={"mode": "auto"})
    assert res.status_code == 404


def test_set_mode_invalid_value_returns_400(monkeypatch):
    job = pipeline.ProductionJob(job_id="job-mode-1")
    monkeypatch.setitem(pipeline._JOBS, "job-mode-1", job)
    res = client.post("/api/production/job-mode-1/mode", json={"mode": "khong-hop-le"})
    assert res.status_code == 400


def test_set_mode_switches_and_unblocks_waiting_job(monkeypatch):
    job = pipeline.ProductionJob(job_id="job-mode-2", run_mode="review")
    job.awaiting_review_scene = 3
    monkeypatch.setitem(pipeline._JOBS, "job-mode-2", job)
    res = client.post("/api/production/job-mode-2/mode", json={"mode": "auto"})
    assert res.status_code == 200
    body = res.json()
    assert body["run_mode"] == "auto"
    assert job._resume_event.is_set()


def test_approve_scene_unknown_job_returns_404():
    res = client.post("/api/production/khong-ton-tai/scenes/1/approve")
    assert res.status_code == 404


def test_approve_scene_wrong_number_returns_409(monkeypatch):
    job = pipeline.ProductionJob(job_id="job-approve-1", run_mode="review")
    job.awaiting_review_scene = 2
    monkeypatch.setitem(pipeline._JOBS, "job-approve-1", job)
    res = client.post("/api/production/job-approve-1/scenes/5/approve")
    assert res.status_code == 409


def test_approve_scene_correct_number_unblocks(monkeypatch):
    job = pipeline.ProductionJob(job_id="job-approve-2", run_mode="review")
    job.awaiting_review_scene = 2
    monkeypatch.setitem(pipeline._JOBS, "job-approve-2", job)
    res = client.post("/api/production/job-approve-2/scenes/2/approve")
    assert res.status_code == 200
    assert job._resume_event.is_set()


def test_restore_scene_unknown_job_returns_404():
    res = client.post("/api/production/khong-ton-tai/scenes/1/restore")
    assert res.status_code == 404


def test_restore_scene_not_skipped_returns_409(monkeypatch):
    job = pipeline.ProductionJob(job_id="job-restore-1", status="generating_scenes")
    job.scenes[1] = pipeline.SceneProgress(scene_n=1, status="done")
    monkeypatch.setitem(pipeline._JOBS, "job-restore-1", job)
    res = client.post("/api/production/job-restore-1/scenes/1/restore")
    assert res.status_code == 409


def test_restore_scene_after_generating_scenes_phase_returns_409(monkeypatch):
    job = pipeline.ProductionJob(job_id="job-restore-2", status="done")
    job.scenes[1] = pipeline.SceneProgress(scene_n=1, status="skipped")
    monkeypatch.setitem(pipeline._JOBS, "job-restore-2", job)
    res = client.post("/api/production/job-restore-2/scenes/1/restore")
    assert res.status_code == 409


def test_restore_scene_with_existing_video_returns_done(monkeypatch):
    job = pipeline.ProductionJob(job_id="job-restore-3", status="generating_scenes")
    job.scenes[1] = pipeline.SceneProgress(scene_n=1, status="skipped", video_path="/tmp/x.mp4")
    monkeypatch.setitem(pipeline._JOBS, "job-restore-3", job)
    res = client.post("/api/production/job-restore-3/scenes/1/restore")
    assert res.status_code == 200
    body = res.json()
    assert body["scenes"]["1"]["status"] == "done"
    assert body["scenes"]["1"]["has_video"] is True


def test_resolve_failed_scene_unknown_job_returns_404():
    res = client.post("/api/production/khong-ton-tai/scenes/1/resolve-failed?action=skip")
    assert res.status_code == 404


def test_resolve_failed_scene_invalid_action_returns_400(monkeypatch):
    job = pipeline.ProductionJob(job_id="job-failed-1", status="generating_scenes")
    job.scenes[1] = pipeline.SceneProgress(scene_n=1, status="failed")
    monkeypatch.setitem(pipeline._JOBS, "job-failed-1", job)
    res = client.post("/api/production/job-failed-1/scenes/1/resolve-failed?action=khong-hop-le")
    assert res.status_code == 400


def test_resolve_failed_scene_not_failed_returns_409(monkeypatch):
    job = pipeline.ProductionJob(job_id="job-failed-2", status="generating_scenes")
    job.scenes[1] = pipeline.SceneProgress(scene_n=1, status="done")
    monkeypatch.setitem(pipeline._JOBS, "job-failed-2", job)
    res = client.post("/api/production/job-failed-2/scenes/1/resolve-failed?action=skip")
    assert res.status_code == 409


def test_resolve_failed_scene_skip_returns_skipped(monkeypatch):
    job = pipeline.ProductionJob(job_id="job-failed-3", status="generating_scenes")
    job.scenes[1] = pipeline.SceneProgress(scene_n=1, status="failed", error="lỗi giả lập")
    monkeypatch.setitem(pipeline._JOBS, "job-failed-3", job)
    res = client.post("/api/production/job-failed-3/scenes/1/resolve-failed?action=skip")
    assert res.status_code == 200
    assert res.json()["scenes"]["1"]["status"] == "skipped"


def test_scene_video_unknown_job_returns_404():
    res = client.get("/api/production/khong-ton-tai/scenes/1/video")
    assert res.status_code == 404


def test_scene_video_not_ready_returns_404(monkeypatch):
    job = pipeline.ProductionJob(job_id="job-preview-1")
    job.scenes[1] = pipeline.SceneProgress(scene_n=1, status="generating")
    monkeypatch.setitem(pipeline._JOBS, "job-preview-1", job)
    res = client.get("/api/production/job-preview-1/scenes/1/video")
    assert res.status_code == 404


def test_scene_video_serves_file_when_ready(monkeypatch, tmp_path):
    video_file = tmp_path / "scene_01.mp4"
    video_file.write_bytes(b"fake mp4 bytes")
    job = pipeline.ProductionJob(job_id="job-preview-2")
    job.scenes[1] = pipeline.SceneProgress(scene_n=1, status="done", video_path=str(video_file))
    monkeypatch.setitem(pipeline._JOBS, "job-preview-2", job)
    res = client.get("/api/production/job-preview-2/scenes/1/video")
    assert res.status_code == 200
    assert res.content == b"fake mp4 bytes"
