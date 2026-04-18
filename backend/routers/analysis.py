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


def _build_prompt(stock_name: str, stock_code: str, scores: dict) -> str:
    dims = {
        "technical": "技术面",
        "capital": "资金面",
        "fundamental": "基本面",
        "news": "消息面",
        "heat": "市场热度",
    }
    score_lines = "\n".join(f"- {label}：{scores.get(k, 'N/A')}分" for k, label in dims.items())

    return f"""你是一位专业的A股分析师，请从以下五个维度对股票进行独立分析和评价。

股票：{stock_name}({stock_code})
综合评分：{scores.get('total', 'N/A')}分（满分100）

各维度评分：
{score_lines}

请用中文分析，包含以下内容：
1. 从技术面、资金面、基本面、消息面、市场热度五个维度分别评价该股当前状态（每维度1-2句）
2. 整体多空判断及核心逻辑（1-2句）
3. 操作建议：给出短线和趋势两个视角的具体建议（各1-2句）

要求：基于各维度评分独立分析，不依赖具体指标数值，简洁有力，不超过300字。"""


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

    prompt = _build_prompt(stock_name, code, scores)

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
                    "max_tokens": 4096,
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
