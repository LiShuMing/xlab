"""API 路由"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional

from core.logger import get_logger
from agents.orchestrator import SimpleAgentOrchestrator
from modules.report_generator import ReportBuilder, ReportFormatter, ReportFormat

logger = get_logger(__name__)

router = APIRouter()


class AnalysisRequest(BaseModel):
    """分析请求"""

    stock_code: str = Field(..., description="股票代码，如 sh600519, sz000001, AAPL")
    query: str = Field(default="请进行全面分析并给出投资建议", description="分析query")
    temperature: Optional[float] = Field(default=0.3, ge=0, le=1, description="LLM temperature")
    max_tokens: Optional[int] = Field(default=4000, ge=100, le=8000, description="最大 token 数")


class AnalysisResponse(BaseModel):
    """分析响应"""

    success: bool
    report: Optional[str] = None
    error: Optional[str] = None
    stock_code: str
    duration: float = 0.0


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_stock(request: AnalysisRequest) -> AnalysisResponse:
    """分析股票并生成报告"""
    import time

    start_time = time.time()

    try:
        # 创建 Agent 编排器
        orchestrator = SimpleAgentOrchestrator()

        # 执行分析
        state = await orchestrator.analyze(
            stock_code=request.stock_code,
            user_query=request.query,
        )

        if state.error:
            raise HTTPException(status_code=500, detail=state.error)

        duration = time.time() - start_time

        return AnalysisResponse(
            success=True,
            report=state.final_response,
            error=None,
            stock_code=request.stock_code,
            duration=round(duration, 2),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"分析失败：{e}")
        return AnalysisResponse(
            success=False,
            report=None,
            error=str(e),
            stock_code=request.stock_code,
            duration=round(time.time() - start_time, 2),
        )


@router.get("/stocks/{stock_code}/price")
async def get_stock_price(stock_code: str):
    """获取股票实时价格"""
    from modules.data_collector import PriceCollector

    collector = PriceCollector()
    result = await collector.collect(stock_code=stock_code)

    if result.success:
        return {"success": True, "data": result.data}
    else:
        raise HTTPException(status_code=404, detail=result.error)


@router.get("/stocks/{stock_code}/kline")
async def get_kline_data(
    stock_code: str,
    days: int = 90,
    period: str = "day",
):
    """获取 K 线数据"""
    from modules.data_collector import KLineCollector

    collector = KLineCollector()
    result = await collector.collect(stock_code=stock_code, days=days, period=period)

    if result.success:
        return {"success": True, "data": result.data}
    else:
        raise HTTPException(status_code=404, detail=result.error)


@router.get("/stocks/{stock_code}/financials")
async def get_financials(stock_code: str):
    """获取财务指标"""
    from modules.data_collector import FinancialCollector

    collector = FinancialCollector()
    result = await collector.collect(stock_code=stock_code)

    if result.success:
        return {"success": True, "data": result.data}
    else:
        raise HTTPException(status_code=404, detail=result.error)


@router.get("/news")
async def get_news(stock_code: Optional[str] = None, limit: int = 20):
    """获取市场新闻"""
    from modules.data_collector import NewsCollector

    collector = NewsCollector()
    result = await collector.collect(stock_code=stock_code, limit=limit)

    if result.success:
        return {"success": True, "data": result.data}
    else:
        raise HTTPException(status_code=404, detail=result.error)
