"""Synthesis agent for combining specialist outputs into professional investment report.

Based on py-lab/stock_module.py framework with 8-section structure:
1. Company Overview
2. Macro & Sector Context
3. Technical Analysis
4. Financial Health
5. Multi-Lens Investment Case
6. Risk Matrix
7. Position Sizing
8. Overall Recommendation
"""

import json
import re
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


# System prompt based on py-lab stock_module.py
SYSTEM_PROMPT_TEMPLATE = """You are a senior cross-disciplinary investment analyst with deep expertise in fundamental analysis,
technical analysis, macro research, and behavioral finance. You serve a retail investor managing approximately
$30,000 USD in U.S. equities, whose primary objective is capital preservation first, appreciation second.

Analyze every investment through the following lenses simultaneously:

1. Value Investing (Warren Buffett / Charlie Munger): Margin of safety, moat, long-term compounding
2. Business Quality (Duan Yongping): Business model integrity, management quality
3. Technical Analysis (Wall Street Trader): Price action, momentum, key price levels
4. Quant/Risk (Hedge Fund PM): Drawdown control, position sizing, portfolio correlation
5. Fundamental (Sell-side Analyst): EPS, FCF, valuation multiples, peer comparison
6. Long-term (Public Fund Manager): DCF, industry cycle, structural growth
7. Short-term (Active Trader): Catalysts, earnings plays, macro correlation
8. Retail (Individual Investor): Liquidity needs, simplicity, emotional discipline

Output Style Guidelines:
1. 文笔简洁严谨，符合正式书面语，避免口语化与情绪化表达
2. 段落分明，重点内容加粗处理，关键数据以表格呈现
3. 所有专有名词使用英文标注，包括 Ticker、指数名称、财务术语
4. 数据引用须注明来源或时间窗口
5. 避免空泛表述，每项结论须有数据或逻辑支撑
6. 若相关数据不足，明确标注"数据待补充"，不作无依据推断
"""


class SynthesisAgent:
    """Synthesizes specialist analyst outputs into a professional investment report.

    This agent receives structured JSON from four specialist agents and produces
    a final report with 8 sections based on py-lab framework.
    """

    # Section title translations
    SECTION_TITLES = {
        "zh": {
            "company_overview": "公司概览",
            "macro_sector": "宏观与行业背景",
            "technical_analysis": "技术面分析",
            "financial_health": "基本面与财务健康",
            "multi_lens": "多视角投资论点",
            "risk_matrix": "风险矩阵",
            "position_sizing": "仓位建议",
            "recommendation": "综合评级",
        },
        "en": {
            "company_overview": "Company Overview",
            "macro_sector": "Macro & Sector Context",
            "technical_analysis": "Technical Analysis",
            "financial_health": "Financial Health",
            "multi_lens": "Multi-Lens Investment Case",
            "risk_matrix": "Risk Matrix",
            "position_sizing": "Position Sizing",
            "recommendation": "Overall Recommendation",
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
        price_data: dict,
        financial_data: dict,
    ) -> str:
        """Build the synthesis prompt for the LLM.

        Args:
            tech: Technical analysis output.
            fund: Fundamental analysis output.
            risk: Risk analysis output.
            sector: Sector analysis output.
            price_data: Real-time price data from tools.
            financial_data: Financial metrics from tools.

        Returns:
            Full synthesis prompt string.
        """
        language_instruction = "Chinese" if self.lang == "zh" else "English"

        # Extract current price from price_data
        current_price = price_data.get("current_price", 0)
        high_52w = price_data.get("high_52w", 0)
        low_52w = price_data.get("low_52w", 0)
        ma_50 = price_data.get("ma_50", 0)
        ma_200 = price_data.get("ma_200", 0)

        # Calculate price position
        price_position = 0
        if high_52w > 0 and low_52w > 0 and high_52w != low_52w and current_price > 0:
            price_position = ((current_price - low_52w) / (high_52w - low_52w)) * 100

        # Calculate MA distances
        dist_ma_50 = 0
        dist_ma_200 = 0
        if ma_50 > 0 and current_price > 0:
            dist_ma_50 = ((current_price - ma_50) / ma_50) * 100
        if ma_200 > 0 and current_price > 0:
            dist_ma_200 = ((current_price - ma_200) / ma_200) * 100

        # Format specialist outputs
        tech_json = json.dumps({
            "trend": tech.trend,
            "support": tech.support,
            "resistance": tech.resistance,
            "momentum_score": tech.momentum_score,
            "pattern": tech.pattern,
            "near_term_outlook": tech.near_term_outlook,
        }, ensure_ascii=False, indent=2)

        fund_json = json.dumps({
            "pe_ratio": fund.pe_ratio,
            "pb_ratio": fund.pb_ratio,
            "sector_avg_pe": fund.sector_avg_pe,
            "sector_avg_pe_source": fund.sector_avg_pe_source,
            "valuation": fund.valuation,
            "quality_score": fund.quality_score,
            "dcf_low": fund.dcf_low,
            "dcf_high": fund.dcf_high,
            "key_metric_comment": fund.key_metric_comment,
        }, ensure_ascii=False, indent=2)

        risk_json = json.dumps({
            "risks": [{"description": r.description, "probability": r.probability, "impact": r.impact} for r in risk.risks],
            "hedge_suggestion": risk.hedge_suggestion,
        }, ensure_ascii=False, indent=2)

        sector_json = json.dumps({
            "sector": sector.sector,
            "positioning": sector.positioning,
            "comps": [{"name": c.name, "code": c.code, "pe": c.pe, "relative_val": c.relative_val} for c in sector.comps],
            "tailwinds": sector.tailwinds,
            "headwinds": sector.headwinds,
            "catalysts": [{"event": c.event, "timing": c.timing, "impact": c.impact} for c in sector.catalysts],
        }, ensure_ascii=False, indent=2)

        return f"""{SYSTEM_PROMPT_TEMPLATE}

=== CURRENT PRICE DATA (CRITICAL - USE THESE EXACT VALUES) ===
Stock: {self.stock_code}
Current Price: ${current_price:.2f}
52-Week Range: ${low_52w:.2f} - ${high_52w:.2f}
Price Position in 52W Range: {price_position:.1f}% (0% = 52W low, 100% = 52W high)
50-Day MA: ${ma_50:.2f}
200-Day MA: ${ma_200:.2f}

Distance from MAs:
- Distance to 50-Day MA: {dist_ma_50:+.1f}%
- Distance to 200-Day MA: {dist_ma_200:+.1f}%

Position Sizing Reference ($30,000 Portfolio):
- Conservative (5%): $1,500 ÷ ${current_price:.2f} = {int(1500/current_price) if current_price > 0 else 0} shares
- Moderate (10%): $3,000 ÷ ${current_price:.2f} = {int(3000/current_price) if current_price > 0 else 0} shares
- Aggressive (15%): $4,500 ÷ ${current_price:.2f} = {int(4500/current_price) if current_price > 0 else 0} shares

=== SPECIALIST ANALYSIS ===

TECHNICAL ANALYSIS:
{tech_json}

FUNDAMENTAL ANALYSIS:
{fund_json}

RISK ANALYSIS:
{risk_json}

SECTOR ANALYSIS:
{sector_json}

---

Generate a comprehensive investment report with the following 8 sections IN ORDER:

## 一、公司概览 Company Overview
- 主营业务与商业模式，核心竞争优势（护城河 Moat）
- 行业地位与主要竞争对手
- 管理层质量与历史资本配置表现

## 二、宏观与行业背景 Macro & Sector Context
- 当前宏观环境对该股的具体影响（利率敏感性、汇率风险、政策暴露）
- 行业所处周期阶段：成长期 Growth / 成熟期 Mature / 衰退期 Decline
- 近期关键催化剂（Catalyst）或逆风因素（Headwind）

## 三、技术面分析 Technical Analysis

**当前价格定位 Current Price Position**
- 当前价格相对于52周区间：精确计算 (当前价-52周低)/(52周高-52周低) 百分比位置
- 与MA(50)/MA(200)的偏离度：计算百分比并判断趋势强度
- 关键价格水平：支撑位 Support、压力位 Resistance

**趋势与动量 Trend & Momentum**
- 趋势判断：价格与MA(50)/MA(200)的关系，金叉/死叉状态
- MACD与RSI当前读数及信号
- 成交量结构与异常信号

**短线交易视角 Short-term Trading View**
- 基于当前价格 ${current_price:.2f} 的精确入场点
- 目标价与止损位（基于当前价格计算R/R比）
- 明确的出场节点评估

## 四、基本面与财务健康 Financial Health
- 盈利质量：Revenue 增长趋势、EPS 走势、Net Margin、FCF Yield
- 资产负债表：D/E Ratio、Current Ratio、Interest Coverage Ratio
- 估值水平：P/E、P/S、EV/EBITDA，对比历史均值与同业水平
- 股东回报：Buyback 规模、Dividend 政策、ROIC / ROE 水平

## 五、多视角投资论点 Multi-Lens Investment Case

巴菲特视角 Buffett Lens:
是否具备持久竞争优势？10年后的业务是否更为强大？当前价格是否提供足够的安全边际（Margin of Safety）？

段永平视角 Duan Yongping Lens:
管理层是否"本分"，商业模式是否正直可持续？以当前估值，能否长期持有而无持续性焦虑？

华尔街交易员视角 Trader Lens:
近期核心催化剂为何？期权市场隐含波动率（IV）是否合理定价？当前风险/回报比（Risk/Reward Ratio）是否具备交易价值？

量化与私募视角 Quant / Hedge Fund Lens:
因子暴露如何（成长 Growth / 价值 Value / 动量 Momentum / 质量 Quality）？与现有持仓的相关性？预期最大回撤（Max Drawdown）区间？

## 六、风险矩阵 Risk Matrix
| 风险类型 | 具体描述 | 发生概率 | 潜在影响 | 缓解措施 |
|---|---|---|---|---|
| 基本面风险 Fundamental Risk | | | | |
| 估值风险 Valuation Risk | | | | |
| 宏观与利率风险 Macro / Rate Risk | | | | |
| 行业竞争风险 Competitive Risk | | | | |
| 流动性与尾部风险 Liquidity / Tail Risk | | | | |

## 七、仓位建议 Position Sizing（基于 $30,000 账户，按当前价格 ${current_price:.2f} 计算）
- 建议仓位比例：占组合 X%，约 $X,XXX
- 精确建仓方案：
  - 当前价格：${current_price:.2f}
  - 建议购买股数：XXX 股
  - 分批策略：首仓 XXX 股 @ ${current_price:.2f}，回调至 $XX.XX 补仓 XXX 股
- 止损位 Stop-Loss：设于 $XX.XX（距离当前价格 -X.X%），潜在损失 $XXX
- 目标价与收益（基于当前价格 ${current_price:.2f}）：
  - 短线目标（1—3个月）：$XX.XX (+X.X%)
  - 中线目标（6—12个月）：$XX.XX (+X.X%)
  - 长线目标（2—3年）：$XX.XX (+X.X%)
- 风险/回报比 Risk/Reward Ratio：1:X
- 建议持仓期限：短线 / 中线 / 长线

## 八、综合评级 Overall Recommendation
```
评级：强烈买入 Strong Buy / 买入 Buy / 观望 Hold / 减持 Underweight / 回避 Avoid
置信度：高 High / 中 Medium / 低 Low
核心投资逻辑（1—2句）：
最重要的下行风险（1句）：
```

---

CRITICAL INSTRUCTIONS:
1. ALL price references MUST use the exact current price ${current_price:.2f}
2. Calculate exact percentage moves from current price
3. Calculate exact share counts for position sizing
4. Use the specialist JSON data for sections 3-6
5. Write in {language_instruction}
6. Return ONLY a JSON object (no markdown fences)

Return JSON format:
{{
  "company_overview": "公司概览内容",
  "macro_sector": "宏观与行业背景内容",
  "technical_analysis": "技术面分析内容（包含价格定位、趋势动量、短线交易视角）",
  "financial_health": "基本面与财务健康内容",
  "multi_lens": "多视角投资论点内容（巴菲特、段永平、交易员、量化视角）",
  "risk_matrix": "风险矩阵表格内容",
  "position_sizing": "仓位建议内容",
  "recommendation": "Buy/Hold/Sell",
  "conviction": "high/medium/low",
  "target_price": {current_price * 1.15:.2f},
  "stop_loss": {current_price * 0.95:.2f},
  "bull_case": "乐观情景描述及目标价",
  "base_case": "中性情景描述及目标价",
  "bear_case": "悲观情景描述及目标价",
  "summary": "1-2句核心投资逻辑"
}}"""

    async def synthesize(
        self,
        tech: TechnicalOutput,
        fund: FundamentalOutput,
        risk: RiskOutput,
        sector: SectorOutput,
        raw_data: dict,
    ) -> Report:
        """Synthesize specialist outputs into a professional report.

        Args:
            tech: Technical analysis output.
            fund: Fundamental analysis output.
            risk: Risk analysis output.
            sector: Sector analysis output.
            raw_data: Raw collected data dict.

        Returns:
            Complete Report object.
        """
        # Extract price data from raw_data
        price_data = self._extract_price_data(raw_data)
        financial_data = self._extract_financial_data(raw_data)

        # Build and call LLM
        prompt = self._build_synthesis_prompt(tech, fund, risk, sector, price_data, financial_data)

        response = await self.llm_client.model.ainvoke([HumanMessage(content=prompt)])
        content = self._strip_markdown_fences(response.content)

        try:
            report_data = json.loads(content)
        except json.JSONDecodeError:
            report_data = self._get_default_report_data(price_data)

        # Build Report object
        report = self._build_report(report_data, tech, fund, risk, sector, raw_data, price_data)

        return report

    def _extract_price_data(self, raw_data: dict) -> dict:
        """Extract price data from raw_data."""
        price_data = {
            "current_price": 0,
            "high_52w": 0,
            "low_52w": 0,
            "ma_50": 0,
            "ma_200": 0,
            "volume": 0,
        }

        # Try to extract from query_stock_price tool result
        if "query_stock_price" in raw_data:
            result = raw_data["query_stock_price"]
            if result and hasattr(result, "metadata") and result.metadata:
                raw = result.metadata.get("raw_data", {})
                if raw:
                    price_data["current_price"] = raw.get("current_price", 0) or 0
                    price_data["volume"] = raw.get("volume", 0) or 0
                    # Use high/low if available
                    if raw.get("high"):
                        price_data["high_52w"] = raw.get("high", 0)
                    if raw.get("low"):
                        price_data["low_52w"] = raw.get("low", 0)

        # Try to extract from query_kline_data tool result
        if "query_kline_data" in raw_data:
            result = raw_data["query_kline_data"]
            if result and hasattr(result, "metadata") and result.metadata:
                raw = result.metadata.get("raw_data", {})
                if raw and isinstance(raw, dict):
                    klines = raw.get("klines", [])
                    if klines and isinstance(klines, list):
                        # Calculate high/low from kline data
                        highs = [k.get("high", 0) for k in klines if k.get("high")]
                        lows = [k.get("low", float("inf")) for k in klines if k.get("low")]

                        if highs:
                            max_high = max(highs)
                            if max_high > price_data["high_52w"]:
                                price_data["high_52w"] = max_high

                        if lows and min(lows) < float("inf"):
                            min_low = min(lows)
                            if price_data["low_52w"] == 0 or min_low < price_data["low_52w"]:
                                price_data["low_52w"] = min_low

        # Fallback: if we have current_price but no high/low, estimate based on typical volatility
        if price_data["current_price"] > 0:
            if price_data["high_52w"] == 0:
                price_data["high_52w"] = price_data["current_price"] * 1.15  # Estimate 15% above current
            if price_data["low_52w"] == 0:
                price_data["low_52w"] = price_data["current_price"] * 0.85  # Estimate 15% below current

        return price_data

    def _extract_financial_data(self, raw_data: dict) -> dict:
        """Extract financial data from raw_data."""
        financial_data = {
            "pe_ratio": None,
            "pb_ratio": None,
            "market_cap": None,
            "revenue_growth": None,
            "profit_margin": None,
        }

        if "query_financial_metrics" in raw_data:
            result = raw_data["query_financial_metrics"]
            if result and hasattr(result, "content") and result.content:
                content = result.content
                if isinstance(content, dict):
                    financial_data.update(content)

        return financial_data

    def _strip_markdown_fences(self, text: str) -> str:
        """Strip markdown fences from text."""
        return re.sub(r"^```json\s*|\s*```$", "", text, flags=re.DOTALL).strip()

    def _get_default_report_data(self, price_data: dict) -> dict:
        """Get default report data when LLM parsing fails."""
        current_price = price_data.get("current_price", 0)
        return {
            "company_overview": "需要进一步分析",
            "macro_sector": "宏观与行业背景待分析",
            "technical_analysis": "技术面分析待补充",
            "financial_health": "基本面分析待补充",
            "multi_lens": "多视角投资论点待补充",
            "risk_matrix": "风险矩阵待补充",
            "position_sizing": "仓位建议待补充",
            "recommendation": "Hold",
            "conviction": "medium",
            "target_price": current_price * 1.1 if current_price else None,
            "stop_loss": current_price * 0.95 if current_price else None,
            "bull_case": "乐观情景待分析",
            "base_case": "中性情景待分析",
            "bear_case": "悲观情景待分析",
            "summary": "需要进一步分析",
        }

    def _build_report(
        self,
        report_data: dict,
        tech: TechnicalOutput,
        fund: FundamentalOutput,
        risk: RiskOutput,
        sector: SectorOutput,
        raw_data: dict,
        price_data: dict,
    ) -> Report:
        """Build Report object from synthesis data."""
        current_price = price_data.get("current_price", 0)

        report = Report(
            stock_code=self.stock_code,
            stock_name=sector.sector if sector.sector else "",
            report_id=f"{self.stock_code}_{datetime.now().strftime('%Y%m%d_%H%M')}",
            title=f"{self.stock_code} 投资分析报告",
            summary=report_data.get("summary", report_data.get("company_overview", "")),
            rating=report_data.get("recommendation", "Hold"),
            confidence=report_data.get("conviction", "medium"),
            target_price=report_data.get("target_price"),
            bull_case=report_data.get("bull_case"),
            bear_case=report_data.get("bear_case"),
            base_case=report_data.get("base_case"),
            raw_data=raw_data,
        )

        # Add sections in order (8 sections)
        sections = [
            ReportSection(
                title=self.titles["company_overview"],
                content=report_data.get("company_overview", ""),
                order=1,
            ),
            ReportSection(
                title=self.titles["macro_sector"],
                content=report_data.get("macro_sector", ""),
                order=2,
            ),
            ReportSection(
                title=self.titles["technical_analysis"],
                content=report_data.get("technical_analysis", ""),
                order=3,
            ),
            ReportSection(
                title=self.titles["financial_health"],
                content=report_data.get("financial_health", ""),
                order=4,
            ),
            ReportSection(
                title=self.titles["multi_lens"],
                content=report_data.get("multi_lens", ""),
                order=5,
            ),
            ReportSection(
                title=self.titles["risk_matrix"],
                content=report_data.get("risk_matrix", ""),
                order=6,
            ),
            ReportSection(
                title=self.titles["position_sizing"],
                content=report_data.get("position_sizing", f"基于当前价格 ${current_price:.2f}，建议仓位占组合5-10%"),
                order=7,
            ),
            ReportSection(
                title=self.titles["recommendation"],
                content=f"**评级**: {report_data.get('recommendation', 'Hold')}\n\n"
                        f"**置信度**: {report_data.get('conviction', 'medium')}\n\n"
                        f"**目标价**: ${report_data.get('target_price', 'N/A')}\n\n"
                        f"**止损位**: ${report_data.get('stop_loss', 'N/A')}",
                order=8,
            ),
        ]

        report.sections = sections
        return report