from fastapi.testclient import TestClient

from app.api import quality as quality_api
from app.main import app
from app.services.quality_review import ScriptScore, VideoMetadata, CriterionScore

client = TestClient(app)


def test_score_endpoint(monkeypatch):
    fake = ScriptScore(
        criteria=[CriterionScore(key="hook", score=9, comment="Tốt")],
        total_score=9.0,
        summary="Ổn.",
    )
    monkeypatch.setattr(quality_api, "score_script", lambda text: fake)
    res = client.post("/api/quality/score", json={"script_text": "abc"})
    assert res.status_code == 200
    data = res.json()
    assert data["total_score"] == 9.0
    assert data["criteria"][0]["key"] == "hook"


def test_metadata_endpoint(monkeypatch):
    fake = VideoMetadata(
        titles=["T1", "T2"], subtitle="S", descriptions=["D1"], cta_texts=["C1"], thumbnail_texts=["Th1"]
    )
    monkeypatch.setattr(quality_api, "generate_metadata", lambda text: fake)
    res = client.post("/api/quality/metadata", json={"script_text": "abc"})
    assert res.status_code == 200
    assert res.json() == {
        "titles": ["T1", "T2"], "subtitle": "S", "descriptions": ["D1"],
        "cta_texts": ["C1"], "thumbnail_texts": ["Th1"],
    }


def test_score_rejects_empty_text():
    res = client.post("/api/quality/score", json={"script_text": ""})
    assert res.status_code == 422


def test_seo_endpoint_for_each_platform(monkeypatch):
    def fake_seo(script_text, platform):
        from app.services.quality_review import SeoMetadata

        return SeoMetadata(platform=platform, title="T", caption_or_description="C", hashtags=["#a"], tip="Tip")

    monkeypatch.setattr(quality_api, "generate_seo_metadata", fake_seo)
    for platform in ["youtube", "tiktok", "facebook_instagram"]:
        res = client.post("/api/quality/seo", json={"script_text": "abc", "platform": platform})
        assert res.status_code == 200
        assert res.json()["platform"] == platform


def test_seo_endpoint_rejects_unknown_platform():
    res = client.post("/api/quality/seo", json={"script_text": "abc", "platform": "myspace"})
    assert res.status_code == 400
