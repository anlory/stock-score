import logging
import time
import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_session, upsert
from backend.models import Score, Stock, DailyData
from backend.config import AI_API_KEY, AI_BASE_URL, AI_MODEL

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analysis", tags=["analysis"])


def _build_prompt(stock_name: str, stock_code: str, scores: dict, profile=None, trend_info=None) -> str:
    dims = {
        "technical": "技术面",
        "capital": "资金面",
        "fundamental": "基本面",
        "news": "消息面",
        "heat": "市场热度",
    }
    score_lines = "\n".join(f"- {label}：{scores.get(k, 'N/A')}分" for k, label in dims.items())

    profile_block = "（暂无公司资料）"
    if profile:
        parts = []
        if profile.get("business"):
            parts.append(f"主营业务：{profile['business']}")
        if profile.get("industry"):
            parts.append(f"所属行业：{profile['industry']}")
        concepts = profile.get("concepts") or []
        if concepts:
            parts.append(f"概念板块：{', '.join(concepts)}")
        if parts:
            profile_block = "\n".join(parts)

    trend_block = "（暂无近期走势数据）"
    if trend_info:
        lines = []
        r5, r20, r60 = trend_info.get("return_5d"), trend_info.get("return_20d"), trend_info.get("return_60d")
        if any(v is not None for v in (r5, r20, r60)):
            lines.append(f"个股涨跌：近5日 {r5}%，近20日 {r20}%，近60日 {r60}%")
        ic, ic5, ic20 = trend_info.get("industry_change"), trend_info.get("industry_change_5d"), trend_info.get("industry_change_20d")
        if any(v is not None for v in (ic, ic5, ic20)):
            lines.append(f"行业涨跌：今日 {ic}%，近5日 {ic5}%，近20日 {ic20}%")
        tags = trend_info.get("pattern_tags") or []
        if tags:
            lines.append(f"技术形态：{', '.join(tags)}")
        if lines:
            trend_block = "\n".join(lines)

    return f"""你是一位专业的A股分析师，请基于以下信息对股票出具结构化研判。

股票：{stock_name}({stock_code})
综合评分：{scores.get('total', 'N/A')}分（满分100）

各维度评分：
{score_lines}

公司与板块：
{profile_block}

近期表现：
{trend_block}

请用中文 markdown 输出，严格按以下 4 段结构，每段用 `## 标题` 开头：

## 公司概况
一句话概括主营业务与所处行业地位。

## 板块关联
基于所属行业/概念，结合板块近期表现，分析板块强弱对个股的影响（2-3句）。

## 近期走势
结合 5/20/60 日涨跌与技术形态标签，判断当前走势位置（2-3句）。

## 综合研判
给出多空判断、核心逻辑，以及短线与趋势两个视角的操作建议。

全文不超过 600 字，语言简洁有力，避免空话。"""


@router.get("/{code}")
def analyze_stock(code: str, session: Session = Depends(get_session)):
    if not AI_API_KEY:
        raise HTTPException(400, "未配置 GLM_API_KEY，请设置环境变量后重启服务")

    code = code.zfill(6)

    stock = session.get(Stock, code)
    score = session.query(Score).filter(
        Score.code == code, Score.strategy == "trend"
    ).order_by(Score.date.desc()).first()
    if not score:
        score = session.query(Score).filter(
            Score.code == code
        ).order_by(Score.date.desc()).first()
    if not score:
        raise HTTPException(404, "暂无评分数据")

    latest_date = score.date
    daily = session.query(DailyData).filter(
        DailyData.code == code, DailyData.date == latest_date
    ).first()

    # 优先读缓存
    if daily and daily.ai_analysis:
        return {"analysis": daily.ai_analysis, "cached": True}

    stock_name = stock.name if stock else code
    scores = {
        "total": score.total_score,
        "technical": score.technical_score,
        "capital": score.capital_score,
        "fundamental": score.fundamental_score,
        "news": score.news_score,
        "heat": score.heat_score,
    }

    profile_payload = None
    if stock:
        try:
            import json as _json
            concepts = _json.loads(stock.concepts or "[]")
        except Exception:
            concepts = []
        profile_payload = {
            "business": stock.business,
            "industry": stock.industry,
            "concepts": concepts,
        }

    trend_info_payload = None
    if daily:
        try:
            import json as _json
            pattern_tags = _json.loads(daily.pattern_tags or "[]")
        except Exception:
            pattern_tags = []
        trend_info_payload = {
            "return_5d": daily.return_5d, "return_20d": daily.return_20d, "return_60d": daily.return_60d,
            "industry_change": daily.industry_change,
            "industry_change_5d": daily.industry_change_5d,
            "industry_change_20d": daily.industry_change_20d,
            "pattern_tags": pattern_tags,
        }

    prompt = _build_prompt(stock_name, code, scores, profile_payload, trend_info_payload)

    last_err = None
    for attempt in range(3):
        try:
            r = httpx.post(
                f"{AI_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {AI_API_KEY}"},
                json={
                    "model": AI_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 6144,
                },
                timeout=120,
            )
            if r.status_code == 429 and attempt < 2:
                wait = 2 ** (attempt + 1)
                logger.warning(f"AI rate limited, retry {attempt+1}/3 in {wait}s")
                time.sleep(wait)
                continue
            r.raise_for_status()
            msg = r.json()["choices"][0]["message"]
            content = msg.get("content") or msg.get("reasoning_content", "")

            # 写入缓存
            if daily:
                daily.ai_analysis = content
                session.commit()
            else:
                upsert(session, DailyData, {"code": code, "date": latest_date, "ai_analysis": content}, ["code", "date"])
                session.commit()

            return {"analysis": content}
        except httpx.HTTPStatusError as e:
            last_err = f"AI 服务返回错误: {e.response.status_code}"
            logger.error(f"AI API error: {e.response.status_code} {e.response.text}")
        except Exception as e:
            last_err = f"AI 分析失败: {e}"
            logger.error(f"AI analysis failed: {e}")
    raise HTTPException(502, last_err or "AI 分析失败")
