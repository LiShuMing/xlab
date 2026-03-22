"""API routes for stock analysis endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from core.logger import get_logger
from agents.orchestrator import SimpleAgentOrchestrator

logger = get_logger(__name__)

router = APIRouter()


class AnalysisRequest(BaseModel):
    """Analysis request model.

    Attributes:
        stock_code: Stock ticker symbol.
        query: Analysis query or instructions.
        temperature: LLM temperature (0.0-1.0).
        max_tokens: Maximum tokens in response.
    """

    stock_code: str = Field(..., description="Stock code (e.g., sh600519, sz000001, AAPL)")
    query: str = Field(
        default="Please provide comprehensive analysis and investment recommendations",
        description="Analysis query",
    )
    temperature: Optional[float] = Field(default=0.3, ge=0, le=1, description="LLM temperature")
    max_tokens: Optional[int] = Field(default=4000, ge=100, le=8000, description="Max tokens")


class AnalysisResponse(BaseModel):
    """Analysis response model.

    Attributes:
        success: Whether analysis succeeded.
        report: Generated report (if successful).
        error: Error message (if failed).
        stock_code: Stock code analyzed.
        duration: Analysis duration in seconds.
    """

    success: bool
    report: Optional[str] = None
    error: Optional[str] = None
    stock_code: str
    duration: float = 0.0


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_stock(request: AnalysisRequest) -> AnalysisResponse:
    """Analyze stock and generate investment report.

    Args:
        request: Analysis request with stock code and query.

    Returns:
        Analysis response with generated report.
    """
    import time

    start_time = time.time()

    try:
        orchestrator = SimpleAgentOrchestrator()

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
        logger.error(f"Analysis failed: {e}")
        return AnalysisResponse(
            success=False,
            report=None,
            error=str(e),
            stock_code=request.stock_code,
            duration=round(time.time() - start_time, 2),
        )


@router.get("/stocks/{stock_code}/price")
async def get_stock_price(stock_code: str):
    """Get stock real-time price.

    Args:
        stock_code: Stock ticker symbol.

    Returns:
        Price data dictionary.
    """
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
    """Get stock K-line data.

    Args:
        stock_code: Stock ticker symbol.
        days: Number of days to fetch.
        period: Period type (day/week/month).

    Returns:
        K-line data dictionary.
    """
    from modules.data_collector import KLineCollector

    collector = KLineCollector()
    result = await collector.collect(stock_code=stock_code, days=days, period=period)

    if result.success:
        return {"success": True, "data": result.data}
    else:
        raise HTTPException(status_code=404, detail=result.error)


@router.get("/stocks/{stock_code}/financials")
async def get_financials(stock_code: str):
    """Get stock financial metrics.

    Args:
        stock_code: Stock ticker symbol.

    Returns:
        Financial metrics dictionary.
    """
    from modules.data_collector import FinancialCollector

    collector = FinancialCollector()
    result = await collector.collect(stock_code=stock_code)

    if result.success:
        return {"success": True, "data": result.data}
    else:
        raise HTTPException(status_code=404, detail=result.error)


@router.get("/news")
async def get_news(stock_code: Optional[str] = None, limit: int = 20):
    """Get market news.

    Args:
        stock_code: Optional stock code for stock-specific news.
        limit: Number of news items to return.

    Returns:
        News data dictionary.
    """
    from modules.data_collector import NewsCollector

    collector = NewsCollector()
    result = await collector.collect(stock_code=stock_code, limit=limit)

    if result.success:
        return {"success": True, "data": result.data}
    else:
        raise HTTPException(status_code=404, detail=result.error)
