"""Specialist analyst agents for perspective-decomposed investment analysis."""

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from core.llm import LLMClient, HumanMessage


# =============================================================================
# Output Dataclasses (Typed Schemas)
# =============================================================================


@dataclass
class TechnicalOutput:
    """Technical analysis output schema."""
    trend: str = "sideways"  # bullish|bearish|sideways
    support: Optional[float] = None
    resistance: Optional[float] = None
    momentum_score: int = 5  # 1-10
    pattern: str = "no clear pattern"
    near_term_outlook: str = ""


@dataclass
class FundamentalOutput:
    """Fundamental analysis output schema."""
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    sector_avg_pe: Optional[float] = None
    sector_avg_pe_source: str = "llm_estimate"  # akshare|llm_estimate
    valuation: str = "fairly valued"  # undervalued|fairly valued|overvalued
    quality_score: int = 5  # 1-10
    dcf_low: Optional[float] = None
    dcf_high: Optional[float] = None
    key_metric_comment: str = ""


@dataclass
class RiskItem:
    """Individual risk item."""
    description: str = ""
    probability: str = "medium"  # high|medium|low
    impact: str = "medium"  # high|medium|low


@dataclass
class RiskOutput:
    """Risk analysis output schema."""
    risks: list[RiskItem] = field(default_factory=list)
    hedge_suggestion: str = "none"


@dataclass
class ComparableCompany:
    """Comparable company info."""
    name: str = ""
    code: str = ""
    pe: Optional[float] = None
    relative_val: str = "fairly valued"  # cheaper|fairly valued|expensive


@dataclass
class Catalyst:
    """Catalyst event."""
    event: str = ""
    timing: str = ""
    impact: str = "neutral"  # positive|negative|neutral


@dataclass
class SectorOutput:
    """Sector analysis output schema."""
    sector: str = ""
    positioning: str = "leader"  # leader|challenger|laggard
    comps: list[ComparableCompany] = field(default_factory=list)
    tailwinds: str = ""
    headwinds: str = ""
    catalysts: list[Catalyst] = field(default_factory=list)

    @classmethod
    def with_llm_fallback(cls, stock_code: str, llm_client: LLMClient) -> "SectorOutput":
        """Create sector output with LLM-estimated comps when AKShare unavailable."""
        prompt = f"""You are a sector analyst. Provide 2-3 comparable companies for {stock_code}.

Return ONLY a JSON array with this exact structure:
[
  {{"name": "Company A", "code": "ticker", "pe": 20.0, "relative_val": "cheaper"}},
  {{"name": "Company B", "code": "ticker", "pe": 25.0, "relative_val": "fairly valued"}}
]

Use real competitor names and approximate P/E ratios. Be specific."""

        try:
            response = llm_client.model.invoke([HumanMessage(content=prompt)])
            content = _strip_markdown_fences(response.content)
            comps_data = json.loads(content)
            comps = [
                ComparableCompany(
                    name=c.get("name", ""),
                    code=c.get("code", ""),
                    pe=c.get("pe"),
                    relative_val=c.get("relative_val", "fairly valued")
                )
                for c in comps_data[:3]
            ]
        except Exception:
            comps = [
                ComparableCompany(name="Sector Comp A", code="N/A", pe=20.0, relative_val="fairly valued"),
                ComparableCompany(name="Sector Comp B", code="N/A", pe=22.0, relative_val="fairly valued"),
            ]

        return cls(
            sector="Sector Analysis Required",
            positioning="leader",
            comps=comps,
            tailwinds="Industry tailwinds to be analyzed",
            headwinds="Industry headwinds to be analyzed",
            catalysts=[
                Catalyst(event="Sector update", timing="TBD", impact="neutral"),
                Catalyst(event="Industry trends", timing="TBD", impact="neutral"),
                Catalyst(event="Market conditions", timing="TBD", impact="neutral"),
            ]
        )


# =============================================================================
# Base Specialist Agent
# =============================================================================


def _strip_markdown_fences(text: str) -> str:
    """Strip markdown JSON fences from text."""
    return re.sub(r"^```json\s*|\s*```$", "", text, flags=re.DOTALL).strip()


def _parse_output(text: str, llm_client: LLMClient, retry_prompt: str = None) -> dict:
    """Parse LLM output, stripping fences and retrying on parse error."""
    content = _strip_markdown_fences(text)

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Retry once
        if retry_prompt is None:
            retry_prompt = "Return ONLY the JSON object, no other text:"

        try:
            response = llm_client.model.invoke([HumanMessage(content=retry_prompt)])
            content = _strip_markdown_fences(response.content)
            return json.loads(content)
        except Exception:
            return {}


def format_relevant_data(
    data: dict,
    keys: list[str],
    max_chars: int = 3000
) -> str:
    """Format relevant data from collected data dict.

    Args:
        data: Full collected data dict.
        keys: Keys to extract and format.
        max_chars: Maximum character limit.

    Returns:
        Formatted string of relevant data.
    """
    result_parts = []

    for key in keys:
        if key in data:
            value = data[key]
            # Convert to string if needed
            if hasattr(value, 'content'):
                value_str = str(value.content) if value.content else ""
            else:
                value_str = str(value) if value else ""

            result_parts.append(f"{key}:\n{value_str}")

    result = "\n\n".join(result_parts)

    # Truncate if needed
    if len(result) > max_chars:
        result = result[:max_chars] + "...[truncated]"

    return result


class BaseSpecialistAgent(ABC):
    """Base class for specialist analyst agents."""

    ROLE: str = "Specialist Analyst"
    DATA_KEYS: list[str] = []  # Keys to extract from collected data

    def __init__(self, stock_code: str, llm_client: LLMClient):
        """Initialize specialist agent.

        Args:
            stock_code: Stock ticker symbol.
            llm_client: LLM client instance.
        """
        self.stock_code = stock_code
        self.llm_client = llm_client

    @abstractmethod
    def get_output_schema(self) -> dict:
        """Get output JSON schema example for LLM."""
        pass

    @abstractmethod
    def parse_output(self, data: dict) -> object:
        """Parse LLM JSON output into typed dataclass."""
        pass

    async def analyze(self, data: dict) -> object:
        """Execute specialist analysis.

        Args:
            data: Full collected data dict.

        Returns:
            Typed output dataclass.
        """
        relevant_data = format_relevant_data(
            data,
            self.DATA_KEYS,
            max_chars=3000
        )

        schema_example = json.dumps(
            self.get_output_schema(),
            ensure_ascii=False,
            indent=2
        )

        prompt = f"""You are {self.ROLE}.

Analyze the following data for stock {self.stock_code}:
{relevant_data}

Return ONLY a JSON object (no markdown fences, no prose) with these exact fields:
{schema_example}

Be specific. Use actual numbers from the data. Do not hedge with generic statements."""

        response = await self.llm_client.model.ainvoke([HumanMessage(content=prompt)])
        parsed = _parse_output(
            response.content,
            self.llm_client,
            retry_prompt="Return ONLY the JSON object with the analysis fields, no other text:"
        )

        return self.parse_output(parsed)


# =============================================================================
# Technical Analyst Agent
# =============================================================================


class TechnicalAnalystAgent(BaseSpecialistAgent):
    """Technical analysis specialist."""

    ROLE = "a senior technical analyst at Goldman Sachs, specializing in K-line pattern recognition and momentum analysis"
    DATA_KEYS = ["query_stock_price", "query_kline_data"]

    def get_output_schema(self) -> dict:
        return {
            "trend": "bullish|bearish|sideways",
            "support": 123.45,
            "resistance": 145.00,
            "momentum_score": 7,
            "pattern": "ascending triangle",
            "near_term_outlook": "brief 1-sentence view"
        }

    def parse_output(self, data: dict) -> TechnicalOutput:
        return TechnicalOutput(
            trend=data.get("trend", "sideways"),
            support=data.get("support"),
            resistance=data.get("resistance"),
            momentum_score=min(10, max(1, data.get("momentum_score", 5))),
            pattern=data.get("pattern", "no clear pattern"),
            near_term_outlook=data.get("near_term_outlook", "")
        )


# =============================================================================
# Fundamental Analyst Agent
# =============================================================================


class FundamentalAnalystAgent(BaseSpecialistAgent):
    """Fundamental analysis specialist."""

    ROLE = "a fundamental equity analyst at Morgan Stanley, specializing in valuation analysis and DCF modeling"
    DATA_KEYS = ["query_financial_metrics"]

    def get_output_schema(self) -> dict:
        return {
            "pe_ratio": 28.5,
            "pb_ratio": 4.2,
            "sector_avg_pe": 32.0,
            "sector_avg_pe_source": "akshare|llm_estimate",
            "valuation": "undervalued|fairly valued|overvalued",
            "quality_score": 8,
            "dcf_low": 110.0,
            "dcf_high": 145.0,
            "key_metric_comment": "ROE 28% vs sector 15% — quality premium justified"
        }

    def parse_output(self, data: dict) -> FundamentalOutput:
        source = data.get("sector_avg_pe_source", "llm_estimate")
        if source not in ["akshare", "llm_estimate"]:
            source = "llm_estimate"

        return FundamentalOutput(
            pe_ratio=data.get("pe_ratio"),
            pb_ratio=data.get("pb_ratio"),
            sector_avg_pe=data.get("sector_avg_pe"),
            sector_avg_pe_source=source,
            valuation=data.get("valuation", "fairly valued"),
            quality_score=min(10, max(1, data.get("quality_score", 5))),
            dcf_low=data.get("dcf_low"),
            dcf_high=data.get("dcf_high"),
            key_metric_comment=data.get("key_metric_comment", "")
        )


# =============================================================================
# Risk Officer Agent
# =============================================================================


class RiskOfficerAgent(BaseSpecialistAgent):
    """Risk analysis specialist."""

    ROLE = "a risk officer reviewing this position for potential downside risks"
    DATA_KEYS = []  # Gets all data

    def get_output_schema(self) -> dict:
        return {
            "risks": [
                {
                    "description": "Risk description",
                    "probability": "high|medium|low",
                    "impact": "high|medium|low"
                }
            ],
            "hedge_suggestion": "brief suggestion or 'none'"
        }

    def parse_output(self, data: dict) -> RiskOutput:
        risks_data = data.get("risks", [])
        risks = []

        for r in risks_data[:3]:  # Max 3 risks
            prob = r.get("probability", "medium")
            if prob not in ["high", "medium", "low"]:
                prob = "medium"

            impact = r.get("impact", "medium")
            if impact not in ["high", "medium", "low"]:
                impact = "medium"

            risks.append(RiskItem(
                description=r.get("description", ""),
                probability=prob,
                impact=impact
            ))

        # Ensure at least one risk
        if not risks:
            risks.append(RiskItem(
                description="Market volatility risk",
                probability="medium",
                impact="medium"
            ))

        return RiskOutput(
            risks=risks,
            hedge_suggestion=data.get("hedge_suggestion", "none")
        )


# =============================================================================
# Sector Strategist Agent
# =============================================================================


class SectorStrategistAgent(BaseSpecialistAgent):
    """Sector strategy specialist."""

    ROLE = "a sector strategist covering the industry, specializing in competitive positioning and comparable company analysis"
    DATA_KEYS = ["query_financial_metrics", "query_market_news"]

    def get_output_schema(self) -> dict:
        return {
            "sector": "Consumer Staples",
            "positioning": "leader|challenger|laggard",
            "comps": [
                {
                    "name": "Company A",
                    "code": "ticker",
                    "pe": 25.0,
                    "relative_val": "cheaper"
                }
            ],
            "tailwinds": "1-sentence",
            "headwinds": "1-sentence",
            "catalysts": [
                {
                    "event": "Q1 earnings release",
                    "timing": "2026-04",
                    "impact": "positive"
                }
            ]
        }

    def parse_output(self, data: dict) -> SectorOutput:
        comps_data = data.get("comps", [])
        comps = []

        for c in comps_data[:3]:
            rel_val = c.get("relative_val", "fairly valued")
            if rel_val not in ["cheaper", "fairly valued", "expensive"]:
                rel_val = "fairly valued"

            comps.append(ComparableCompany(
                name=c.get("name", ""),
                code=c.get("code", ""),
                pe=c.get("pe"),
                relative_val=rel_val
            ))

        catalysts_data = data.get("catalysts", [])
        catalysts = []

        for cat in catalysts_data[:5]:
            impact = cat.get("impact", "neutral")
            if impact not in ["positive", "negative", "neutral"]:
                impact = "neutral"

            catalysts.append(Catalyst(
                event=cat.get("event", ""),
                timing=cat.get("timing", ""),
                impact=impact
            ))

        # Ensure minimum 3 catalysts
        while len(catalysts) < 3:
            catalysts.append(Catalyst(
                event="To be determined",
                timing="TBD",
                impact="neutral"
            ))

        positioning = data.get("positioning", "leader")
        if positioning not in ["leader", "challenger", "laggard"]:
            positioning = "leader"

        return SectorOutput(
            sector=data.get("sector", "Sector Analysis Required"),
            positioning=positioning,
            comps=comps,
            tailwinds=data.get("tailwinds", ""),
            headwinds=data.get("headwinds", ""),
            catalysts=catalysts
        )
