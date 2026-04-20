from backend.routers.analysis import _build_prompt


def test_prompt_includes_all_context():
    prompt = _build_prompt(
        stock_name="平安银行",
        stock_code="000001",
        scores={"total": 72, "technical": 75, "capital": 68, "fundamental": 70, "news": 60, "heat": 80},
        profile={
            "business": "主要提供银行业务",
            "industry": "银行",
            "concepts": ["金融改革", "大金融"],
        },
        trend_info={
            "return_5d": 3.2, "return_20d": -1.1, "return_60d": 12.5,
            "industry_change": 0.8, "industry_change_5d": 2.1, "industry_change_20d": -0.5,
            "pattern_tags": ["MA5上穿MA13", "放量上攻"],
        },
    )
    assert "平安银行" in prompt
    assert "银行业务" in prompt
    assert "金融改革" in prompt
    assert "MA5上穿MA13" in prompt
    assert "3.2" in prompt
    assert "公司概况" in prompt
    assert "板块关联" in prompt
    assert "近期走势" in prompt
    assert "综合研判" in prompt


def test_prompt_handles_missing_profile_and_trend():
    prompt = _build_prompt(
        stock_name="某股",
        stock_code="000999",
        scores={"total": 50, "technical": 50, "capital": 50, "fundamental": 50, "news": 50, "heat": 50},
        profile=None,
        trend_info=None,
    )
    assert "某股" in prompt
    assert "公司概况" in prompt
