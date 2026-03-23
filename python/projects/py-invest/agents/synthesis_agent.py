"""Synthesis agent for combining specialist outputs into GS-style investment report."""

import json
from datetime import datetime
from typing import Optional

from core.llm import LLMClient, HumanMessage
from modules.report_generator.types import Report, ReportSection
from agents.specialist_agents import (
    TechnicalOutput,
    FundamentalOutput,
    RiskOutput,
    SectorOutput,
)


class SynthesisAgent:
    """Synthesizes specialist analyst outputs into a Goldman/MS-style investment report.

    This agent receives structured JSON from four specialist agents and produces
    a final report with all 9 GS-style sections.
    """

    # Section title translations
    SECTION_TITLES = {
        "zh": {
            "investment_thesis": "投资论点",
            "price_target_methodology": "目标价与方法论",
            "technical_picture": "技术面分析",
            "fundamental_analysis": "基本面分析",
            "sector_comparables": "行业与可比公司",
            "key_catalysts": "关键催化剂",
            "risk_factors": "风险因素",
            "recommendation": "投资建议",
        },
        "en": {
            "investment_thesis": "Investment Thesis",
            "price_target_methodology": "Price Target & Methodology",
            "technical_picture": "Technical Picture",
            "fundamental_analysis": "Fundamental Analysis",
            "sector_comparables": "Sector & Comparables",
            "key_catalysts": "Key Catalysts",
            "risk_factors": "Risk Factors",
            "recommendation": "Recommendation",
        },
    }

    def __init__(self, stock_code: str, llm_client: LLMClient, lang: str = "zh"):
        """Initialize synthesis agent.

        Args:
            stock_code: Stock ticker symbol.
            llm_client: LLM client instance.
            lang: Output language ("zh" for Chinese, "en" for English).
        """
        self.stock_code = stock_code
        self.llm_client = llm_client
        self.lang = lang
        self.titles = self.SECTION_TITLES.get(lang, self.SECTION_TITLES["zh"])

    def _build_synthesis_prompt(
        self,
        tech: TechnicalOutput,
        fund: FundamentalOutput,
        risk: RiskOutput,
        sector: SectorOutput,
        raw_data_summary: str,
    ) -> str:
        """Build the synthesis prompt for the LLM.

        Args:
            tech: Technical analysis output.
            fund: Fundamental analysis output.
            risk: Risk analysis output.
            sector: Sector analysis output.
            raw_data_summary: Summary of raw data.

        Returns:
            Full synthesis prompt string.
        """

        # Format specialist outputs as JSON for the LLM
        tech_json = json.dumps(
            {
                "trend": tech.trend,
                "support": tech.support,
                "resistance": tech.resistance,
                "momentum_score": tech.momentum_score,
                "pattern": tech.pattern,
                "near_term_outlook": tech.near_term_outlook,
            },
            ensure_ascii=False,
            indent=2,
        )

        fund_json = json.dumps(
            {
                "pe_ratio": fund.pe_ratio,
                "pb_ratio": fund.pb_ratio,
                "sector_avg_pe": fund.sector_avg_pe,
                "sector_avg_pe_source": fund.sector_avg_pe_source,
                "valuation": fund.valuation,
                "quality_score": fund.quality_score,
                "dcf_low": fund.dcf_low,
                "dcf_high": fund.dcf_high,
                "key_metric_comment": fund.key_metric_comment,
            },
            ensure_ascii=False,
            indent=2,
        )

        risk_json = json.dumps(
            {
                "risks": [
                    {"description": r.description, "probability": r.probability, "impact": r.impact}
                    for r in risk.risks
                ],
                "hedge_suggestion": risk.hedge_suggestion,
            },
            ensure_ascii=False,
            indent=2,
        )

        sector_json = json.dumps(
            {
                "sector": sector.sector,
                "positioning": sector.positioning,
                "comps": [
                    {"name": c.name, "code": c.code, "pe": c.pe, "relative_val": c.relative_val}
                    for c in sector.comps
                ],
                "tailwinds": sector.tailwinds,
                "headwinds": sector.headwinds,
                "catalysts": [
                    {"event": c.event, "timing": c.timing, "impact": c.impact}
                    for c in sector.catalysts
                ],
            },
            ensure_ascii=False,
            indent=2,
        )

        return f"""You are the lead analyst writing the final Goldman Sachs/Morgan Stanley-style investment report for stock {self.stock_code}.

You have received analysis from four specialist analysts:

=== TECHNICAL ANALYSIS ===
{tech_json}

=== FUNDAMENTAL ANALYSIS ===
{fund_json}

=== RISK ANALYSIS ===
{risk_json}

=== SECTOR ANALYSIS ===
{sector_json}

=== RAW DATA SUMMARY ===
{raw_data_summary}

---

Your task is to write a comprehensive investment report with the following 9 sections IN ORDER:

1. **Investment Thesis** (2-3 sentences) — The core argument for why buy/sell/hold this stock NOW. Be specific and actionable.

2. **Price Target & Methodology** — State the target price (a real number), the methodology used (DCF / P/E comp / EV/EBITDA), and the upside/downside percentage.
   - For A-shares: Use P/E-based target: sector_avg_pe * EPS_ttm
   - If sector_avg_pe is from "llm_estimate", label it as such

3. **Bull / Base / Bear Cases** — Three DISTINCT scenarios with specific price targets:
   - Bull Case: Optimistic scenario with key assumptions and price target
   - Base Case: Most likely scenario with key assumptions and price target
   - Bear Case: Pessimistic scenario with key assumptions and price target
   Each must have a DIFFERENT price target, not just rephrased prose.

4. **Technical Picture** — Format the technical analyst's findings into readable prose:
   - Trend direction, support/resistance levels, pattern identified, momentum score, near-term outlook
   - REPRODUCE NUMBERS EXACTLY from the Technical Output JSON — do not invent new values

5. **Fundamental Analysis** — Format the fundamental analyst's findings:
   - P/E, P/B vs sector, quality score, DCF range
   - Explicitly state sector_avg_pe_source (akshare or llm_estimate)
   - REPRODUCE NUMBERS EXACTLY — do not invent new values

6. **Sector & Comparables** — Format the sector strategist's findings:
   - Sector name, positioning (leader/challenger/laggard)
   - List all comparable companies with their P/E and relative valuation
   - Sector tailwinds and headwinds
   - REPRODUCE NUMBERS EXACTLY — do not invent new values

7. **Key Catalysts** — Format the sector strategist's catalysts:
   - List all catalysts with timing and impact
   - Minimum 3 catalysts
   - REPRODUCE EXACTLY from Sector Output

8. **Risk Factors** — Format the risk officer's findings:
   - Top 3 risks with probability/impact
   - Hedge suggestions if any
   - REPRODUCE EXACTLY from Risk Output

9. **Recommendation** — Final recommendation:
   - Buy/Hold/Sell
   - Conviction level (high/medium/low)
   - Brief summary of key reasoning

---

IMPORTANT RULES:
- For sections 4-8, REPRODUCE the numbers and facts from the specialist JSON EXACTLY — do not invent new values
- Present specialist data as readable prose, not JSON
- Be specific and data-driven — avoid generic statements
- Write in Chinese (except ticker symbols)
- Use Markdown formatting

Return ONLY a JSON object with these fields (no markdown fences):
{{
  "investment_thesis": "2-3 sentence core argument",
  "target_price": 123.45,
  "target_price_methodology": "P/E comp based on sector average",
  "upside_pct": 15.5,
  "bull_case": "Bull case scenario with price target",
  "base_case": "Base case scenario with price target",
  "bear_case": "Bear case scenario with price target",
  "technical_picture": "Formatted technical analysis",
  "fundamental_analysis": "Formatted fundamental analysis",
  "sector_comparables": "Formatted sector & comps analysis",
  "key_catalysts": "Formatted catalysts list",
  "risk_factors": "Formatted risk factors",
  "recommendation": "Buy|Hold|Sell",
  "conviction": "high|medium|low"
}}"""

    async def synthesize(
        self,
        tech: TechnicalOutput,
        fund: FundamentalOutput,
        risk: RiskOutput,
        sector: SectorOutput,
        raw_data: dict,
    ) -> Report:
        """Synthesize specialist outputs into a GS-style report.

        Args:
            tech: Technical analysis output.
            fund: Fundamental analysis output.
            risk: Risk analysis output.
            sector: Sector analysis output.
            raw_data: Raw collected data dict.

        Returns:
            Complete Report object.
        """
        # Build raw data summary
        raw_data_summary = self._summarize_raw_data(raw_data)

        # Build and call LLM
        prompt = self._build_synthesis_prompt(tech, fund, risk, sector, raw_data_summary)

        response = await self.llm_client.model.ainvoke([HumanMessage(content=prompt)])
        content = self._strip_markdown_fences(response.content)

        try:
            report_data = json.loads(content)
        except json.JSONDecodeError:
            # Fallback to default structure
            report_data = self._get_default_report_data()

        # Build Report object
        report = self._build_report(report_data, tech, fund, risk, sector, raw_data)

        return report

    def _strip_markdown_fences(self, text: str) -> str:
        """Strip markdown fences from text."""
        import re
        return re.sub(r"^```json\s*|\s*```$", "", text, flags=re.DOTALL).strip()

    def _summarize_raw_data(self, raw_data: dict) -> str:
        """Summarize raw data for the synthesis prompt."""
        parts = []

        for key, value in raw_data.items():
            if value:
                if hasattr(value, 'content'):
                    value_str = str(value.content)[:500] if value.content else ""
                else:
                    value_str = str(value)[:500]
                parts.append(f"{key}: {value_str}")

        return "\n\n".join(parts)[:2000]  # Limit summary length

    def _get_default_report_data(self) -> dict:
        """Get default report data when LLM parsing fails."""
        return {
            "investment_thesis": "需要进一步分析",
            "target_price": None,
            "target_price_methodology": "LLM estimate based on available data",
            "upside_pct": 0.0,
            "bull_case": "bull case scenario to be analyzed",
            "base_case": "base case scenario to be analyzed",
            "bear_case": "bear case scenario to be analyzed",
            "technical_picture": "Technical analysis pending",
            "fundamental_analysis": "Fundamental analysis pending",
            "sector_comparables": "Sector analysis pending",
            "key_catalysts": "Catalysts to be determined",
            "risk_factors": "Risk analysis pending",
            "recommendation": "Hold",
            "conviction": "medium",
        }

    def _build_report(
        self,
        report_data: dict,
        tech: TechnicalOutput,
        fund: FundamentalOutput,
        risk: RiskOutput,
        sector: SectorOutput,
        raw_data: dict,
    ) -> Report:
        """Build Report object from synthesis data.

        Args:
            report_data: Parsed LLM response.
            tech: Technical output (for reference).
            fund: Fundamental output (for reference).
            risk: Risk output (for reference).
            sector: Sector output (for reference).
            raw_data: Raw collected data.

        Returns:
            Complete Report object.
        """
        # Extract stock name from raw data if available
        stock_name = ""
        if "query_financial_metrics" in raw_data:
            # Try to extract company name from financial metrics
            pass  # Will be populated by caller if needed

        report = Report(
            stock_code=self.stock_code,
            stock_name=stock_name,
            report_id=f"{self.stock_code}_{datetime.now().strftime('%Y%m%d_%H%M')}",
            title=f"{self.stock_code} Investment Analysis Report",
            summary=report_data.get("investment_thesis", ""),
            rating=report_data.get("recommendation", "Hold"),
            confidence=report_data.get("conviction", "medium"),
            target_price=report_data.get("target_price"),
            bull_case=report_data.get("bull_case"),
            bear_case=report_data.get("bear_case"),
            base_case=report_data.get("base_case"),
            raw_data=raw_data,
        )

        # Add sections in order
        sections = [
            ReportSection(
                title=self.titles["investment_thesis"],
                content=report_data.get("investment_thesis", ""),
                order=1,
            ),
            ReportSection(
                title=self.titles["price_target_methodology"],
                content=f"Target Price: ¥{report_data.get('target_price', 'N/A')}\n\n"
                        f"Methodology: {report_data.get('target_price_methodology', 'N/A')}\n\n"
                        f"Upside/Downside: {report_data.get('upside_pct', 'N/A')}%",
                order=2,
            ),
            ReportSection(
                title=self.titles["technical_picture"],
                content=report_data.get("technical_picture", ""),
                order=4,
            ),
            ReportSection(
                title=self.titles["fundamental_analysis"],
                content=report_data.get("fundamental_analysis", ""),
                order=5,
            ),
            ReportSection(
                title=self.titles["sector_comparables"],
                content=report_data.get("sector_comparables", ""),
                order=6,
            ),
            ReportSection(
                title=self.titles["key_catalysts"],
                content=report_data.get("key_catalysts", ""),
                order=7,
            ),
            ReportSection(
                title=self.titles["risk_factors"],
                content=report_data.get("risk_factors", ""),
                order=8,
            ),
            ReportSection(
                title=self.titles["recommendation"],
                content=f"**Rating**: {report_data.get('recommendation', 'Hold')}\n\n"
                        f"**Conviction**: {report_data.get('conviction', 'medium')}",
                order=9,
            ),
        ]

        report.sections = sections
        return report
