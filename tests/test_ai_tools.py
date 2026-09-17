from app.services.ai_tools import estimate_budget, get_recommended_tools, AI_TOOLS


def test_recommended_tools_nonempty():
    tools = get_recommended_tools()
    assert len(tools) >= 3
    assert all(t.default_recommended for t in tools)


def test_estimate_budget_known_tool():
    result = estimate_budget("vidu", video_seconds=300, retry_buffer_pct=40)
    assert result["known"] is True
    assert result["estimated_usd_low"] == round(300 * 0.03 * 1.4, 2)
    assert result["estimated_usd_high"] == round(300 * 0.08 * 1.4, 2)


def test_estimate_budget_opaque_tool_returns_honest_unknown():
    result = estimate_budget("ltx_studio", video_seconds=300)
    assert result["known"] is False
    assert "không công bố" in result["message"]


def test_estimate_budget_unknown_tool_id_raises():
    try:
        estimate_budget("does-not-exist", 100)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_all_tools_have_working_link():
    for t in AI_TOOLS:
        assert t.link.startswith("https://")
