from app.services import quality_review


def test_score_script_parses_criteria(monkeypatch):
    fake_response = {
        "criteria": [
            {"key": "hook", "score": 8, "comment": "Mở đầu tốt."},
            {"key": "nhip_dung", "score": 6, "comment": "Hơi chậm giữa video."},
        ],
        "summary": "Kịch bản khá ổn, cần chỉnh nhịp độ.",
    }
    monkeypatch.setattr(quality_review, "generate_json", lambda *a, **k: fake_response)

    result = quality_review.score_script("Kịch bản mẫu bất kỳ.")
    assert len(result.criteria) == 2
    assert result.criteria[0].key == "hook"
    assert result.criteria[0].score == 8
    assert result.total_score == 7.0
    assert "nhịp độ" in result.summary.lower()


def test_score_script_handles_llm_failure(monkeypatch):
    monkeypatch.setattr(
        quality_review, "generate_json",
        lambda *a, **k: {"criteria": [], "summary": "Không chấm được điểm."},
    )
    result = quality_review.score_script("Kịch bản mẫu.")
    assert result.criteria == []
    assert result.total_score == 0.0


def test_generate_metadata_parses_fields(monkeypatch):
    fake_response = {
        "titles": ["Quang Trung Đại Phá Quân Thanh", "5 Ngày Thần Tốc"],
        "subtitle": "Mùa xuân Kỷ Dậu, năm 1789",
        "descriptions": ["Một câu chuyện có thật...", "Mô tả khác..."],
        "cta_texts": ["Follow ngay!", "Xem tiếp phần 2"],
        "thumbnail_texts": ["5 NGÀY THẦN TỐC", "ĐẠI PHÁ QUÂN THANH"],
    }
    monkeypatch.setattr(quality_review, "generate_json", lambda *a, **k: fake_response)

    m = quality_review.generate_metadata("Kịch bản mẫu.")
    assert m.titles[0] == "Quang Trung Đại Phá Quân Thanh"
    assert len(m.titles) == 2
    assert m.thumbnail_texts[0] == "5 NGÀY THẦN TỐC"
    assert len(m.descriptions) == 2
    assert len(m.cta_texts) == 2


def test_generate_metadata_empty_on_failure(monkeypatch):
    monkeypatch.setattr(quality_review, "generate_json", lambda *a, **k: {})
    m = quality_review.generate_metadata("Kịch bản mẫu.")
    assert m.titles == []


def test_generate_seo_metadata_rejects_unknown_platform():
    try:
        quality_review.generate_seo_metadata("abc", "khong-ton-tai")
        assert False, "phải ném ValueError"
    except ValueError:
        pass


def test_generate_seo_metadata_youtube(monkeypatch):
    seen_prompts = []

    def fake_generate_json(system, user_prompt, *a, **k):
        seen_prompts.append(system)
        return {
            "title": "Tiêu đề YouTube",
            "caption_or_description": "Mô tả dài cho YouTube...",
            "hashtags": ["#lichsu", "#vietnam"],
            "tip": "Đăng lúc 20h.",
        }

    monkeypatch.setattr(quality_review, "generate_json", fake_generate_json)
    m = quality_review.generate_seo_metadata("Kịch bản mẫu.", "youtube")
    assert m.platform == "youtube"
    assert m.title == "Tiêu đề YouTube"
    assert m.hashtags == ["#lichsu", "#vietnam"]
    assert "YouTube" in seen_prompts[0]


def test_seo_system_prompt_differs_per_platform():
    """Đảm bảo mỗi nền tảng (cả 6) thật sự có 1 bộ quy tắc riêng, không lỡ
    tay dùng chung 1 prompt cho nhiều nút."""
    prompts = {
        platform: quality_review._SEO_SYSTEM_PROMPT_TEMPLATE.format(
            platform_name=quality_review.PLATFORM_NAMES[platform],
            platform_rules=quality_review._PLATFORM_RULES[platform],
        )
        for platform in quality_review.SUPPORTED_PLATFORMS
    }
    assert len(set(prompts.values())) == len(quality_review.SUPPORTED_PLATFORMS) == 6
