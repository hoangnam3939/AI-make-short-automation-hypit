from fastapi.testclient import TestClient

from app.api import publishing as publishing_api
from app.main import app
from app.services import production_pipeline as pipeline
from app.services import publishing

client = TestClient(app)


def test_status_lists_all_platforms():
    res = client.get("/api/publishing/status")
    assert res.status_code == 200
    data = res.json()
    assert "youtube" in data
    assert data["instagram"]["requires_public_video_url"] is True
    assert data["youtube"]["requires_public_video_url"] is False


def test_save_and_clear_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(publishing, "ENV_PATH", tmp_path / ".env")
    res = client.post("/api/publishing/settings/youtube", json={
        "values": {"YOUTUBE_CLIENT_ID": "id", "YOUTUBE_CLIENT_SECRET": "s", "YOUTUBE_REFRESH_TOKEN": "t"}
    })
    assert res.status_code == 200
    assert res.json()["configured"] is True

    res2 = client.delete("/api/publishing/settings/youtube")
    assert res2.status_code == 200
    assert res2.json()["configured"] is False


def test_save_settings_rejects_unknown_platform():
    res = client.post("/api/publishing/settings/myspace", json={"values": {}})
    assert res.status_code == 400


def test_publish_rejects_unfinished_job(monkeypatch):
    job = pipeline.ProductionJob(job_id="job1")
    job.languages["vi-VN"] = pipeline.LanguageResult(language_code="vi-VN", status="building_video")
    monkeypatch.setitem(pipeline._JOBS, "job1", job)

    res = client.post("/api/publishing/publish", json={
        "platform": "youtube", "job_id": "job1", "language_code": "vi-VN",
    })
    assert res.status_code == 409


def test_publish_requires_video_url_for_instagram(monkeypatch, tmp_path):
    video_path = tmp_path / "v.mp4"
    video_path.write_bytes(b"fake")
    job = pipeline.ProductionJob(job_id="job2")
    job.languages["vi-VN"] = pipeline.LanguageResult(
        language_code="vi-VN", status="done", final_video_path=str(video_path)
    )
    monkeypatch.setitem(pipeline._JOBS, "job2", job)

    res = client.post("/api/publishing/publish", json={
        "platform": "instagram", "job_id": "job2", "language_code": "vi-VN",
    })
    assert res.status_code == 400
    assert "URL công khai" in res.json()["detail"]


def test_publish_dispatches_to_correct_platform_function(monkeypatch, tmp_path):
    video_path = tmp_path / "v.mp4"
    video_path.write_bytes(b"fake")
    job = pipeline.ProductionJob(job_id="job3")
    job.languages["vi-VN"] = pipeline.LanguageResult(
        language_code="vi-VN", status="done", final_video_path=str(video_path)
    )
    monkeypatch.setitem(pipeline._JOBS, "job3", job)

    calls = []
    monkeypatch.setattr(
        publishing_api.publishing, "publish_facebook",
        lambda *a, **k: (calls.append((a, k)), publishing.PublishResult(platform="facebook", success=True, post_url="u"))[1],
    )

    res = client.post("/api/publishing/publish", json={
        "platform": "facebook", "job_id": "job3", "language_code": "vi-VN",
        "title": "T", "description": "D", "hashtags": ["#a"],
    })
    assert res.status_code == 200
    assert res.json()["success"] is True
    assert len(calls) == 1
