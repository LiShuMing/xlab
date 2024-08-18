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
        raw_data: dict | None = None,
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

        raw_evidence = self._format_raw_evidence(raw_data or {}, max_chars=7600)

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

=== RAW DATA EVIDENCE ===
Use this evidence to enrich the report. Do not invent missing data; write "数据待补充" when evidence is absent.
{raw_evidence}

---

Generate a comprehensive deep investment report with the following 8 sections IN ORDER.
Depth requirements:
- Each major text section should contain 3-6 substantive paragraphs or a table plus explanatory bullets.
- Every conclusion should explicitly connect to one of: price data, valuation metrics, financial quality, sector position, catalysts, or risk.
- If yfinance/news data is rate limited or missing, state the limitation and explain how it affects confidence.
- The report should be richer and more complete than a fast summary; prioritize clarity, evidence and decision usefulness.

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
  "company_overview": "公司概览内容：业务模型、收入结构、护城河、管理层和关键监控指标，至少4段",
  "macro_sector": "宏观与行业背景内容：行业周期、竞争格局、需求驱动、监管/利率/汇率影响，至少4段",
  "technical_analysis": "技术面分析内容：价格定位、趋势动量、支撑压力、短中期交易计划；数据不足时说明限制",
  "financial_health": "基本面与财务健康内容：估值、盈利质量、现金流、资产负债表、股东回报，必须引用可用指标",
  "multi_lens": "多视角投资论点内容：Buffett、Duan Yongping、Trader、Quant/Risk、Long-term PM 五个视角",
  "risk_matrix": "| 风险类型 | 触发条件 | 证据 | 概率 | 影响 | 缓解/观察指标 |\\n|---|---|---|---|---|---|\\n...",
  "position_sizing": "仓位建议内容：保守/中性/进取三档，买入区间、止损、加仓条件、复盘触发条件",
  "recommendation": "Buy/Hold/Sell",
  "conviction": "high/medium/low",
  "target_price": {current_price * 1.15:.2f},
  "stop_loss": {current_price * 0.95:.2f},
  "bull_case": "乐观情景描述及目标价",
  "base_case": "中性情景描述及目标价",
  "bear_case": "悲观情景描述及目标价",
  "summary": "5-8句核心投资逻辑，包含主要看多理由、最大风险、估值态度和行动建议"
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
        prompt = self._build_synthesis_prompt(tech, fund, risk, sector, price_data, financial_data, raw_data)

        response = await self.llm_client.model.ainvoke([HumanMessage(content=prompt)])
        content = self._strip_markdown_fences(response.content)

        report_data = self._parse_report_json(content, price_data)

        # Build Report object
        report = self._build_report(report_data, tech, fund, risk, sector, raw_data, price_data)

        return report

    async def synthesize_fast(self, raw_data: dict, user_query: str = "") -> Report:
        """Generate a compact but useful report from collected data in one LLM call."""
        price_data = self._extract_price_data(raw_data)
        financial_data = self._extract_financial_data(raw_data)
        evidence = self._format_raw_evidence(raw_data, max_chars=5200)
        current_price = price_data.get("current_price", 0)
        language_instruction = "Chinese" if self.lang == "zh" else "English"

        prompt = f"""{SYSTEM_PROMPT_TEMPLATE}

You are generating a value-investing research note for {self.stock_code}.
User focus: {user_query or "长期价值投资分析"}

Use ONLY the evidence below. If a field is unavailable, say "数据待补充" instead of inventing numbers.

=== EVIDENCE ===
{evidence}

=== CURRENT PRICE SNAPSHOT ===
Current price: {current_price or "数据待补充"}
Financial metrics: {json.dumps(financial_data, ensure_ascii=False, default=str)}

Return ONLY a JSON object in {language_instruction}:
{{
  "company_overview": "业务、收入来源、护城河和关键假设，3-5段",
  "macro_sector": "行业周期、竞争格局、近期催化剂与逆风，3-5段",
  "technical_analysis": "价格位置、趋势、支撑压力位。若数据不足请说明",
  "financial_health": "估值、盈利质量、现金流、资产负债表，必须引用可用指标",
  "multi_lens": "分别用 Buffett、Duan Yongping、Trader、Risk Manager 四个视角给判断",
  "risk_matrix": "| 风险 | 证据 | 概率 | 影响 | 应对 |\\n|---|---|---|---|---|\\n...",
  "position_sizing": "以当前价格 {current_price or 0} 为基础给保守/中性/进取仓位建议；数据不足则给原则",
  "recommendation": "Buy/Hold/Sell/Avoid",
  "conviction": "high/medium/low",
  "target_price": {current_price * 1.12 if current_price else "null"},
  "stop_loss": {current_price * 0.92 if current_price else "null"},
  "bull_case": "乐观情景",
  "base_case": "中性情景",
  "bear_case": "悲观情景",
  "summary": "3-5句可直接阅读的核心投资结论"
}}"""

        response = await self.llm_client.model.ainvoke([HumanMessage(content=prompt)])
        content = self._strip_markdown_fences(response.content)

        report_data = self._parse_report_json(content, price_data)

        return self._build_report(
            report_data,
            TechnicalOutput(),
            FundamentalOutput(),
            RiskOutput(),
            SectorOutput(),
            raw_data,
            price_data,
        )

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
            if result and hasattr(result, "metadata") and result.metadata:
                content = result.metadata.get("raw_data")
                if isinstance(content, dict):
                    financial_data.update({
                        "pe_ratio": content.get("trailing_pe") or content.get("pe_ratio"),
                        "pb_ratio": content.get("price_to_book") or content.get("pb_ratio"),
                        "market_cap": content.get("market_cap"),
                        "revenue_growth": content.get("revenue_growth"),
                        "profit_margin": content.get("profit_margin"),
                    })

        return financial_data

    def _format_raw_evidence(self, raw_data: dict, max_chars: int = 5200) -> str:
        """Format tool output and raw metadata into bounded prompt evidence."""
        parts = []
        for name, result in raw_data.items():
            lines = [f"## {name}"]
            if hasattr(result, "success") and not result.success:
                lines.append(f"error: {result.error}")
            if getattr(result, "result", ""):
                lines.append(str(result.result))
            metadata = getattr(result, "metadata", {}) or {}
            if metadata.get("raw_data"):
                lines.append(json.dumps(metadata["raw_data"], ensure_ascii=False, default=str)[:1800])
            parts.append("\n".join(lines))

        text = "\n\n".join(parts)
        return text[:max_chars] + ("...[truncated]" if len(text) > max_chars else "")

    def _strip_markdown_fences(self, text: str) -> str:
        """Strip markdown fences from text."""
        return re.sub(r"^```json\s*|\s*```$", "", text, flags=re.DOTALL).strip()

    def _parse_report_json(self, content: str, price_data: dict) -> dict:
        """Parse model output into report JSON, preserving useful text on failure."""
        candidates = [content]
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidates.append(content[start:end + 1])

        for candidate in candidates:
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

        report_data = self._get_default_report_data(price_data)
        if content.strip():
            report_data.update({
                "summary": "模型输出未能解析为结构化 JSON，以下保留原始分析文本供阅读。",
                "company_overview": content.strip(),
                "macro_sector": "结构化解析失败，建议重新生成或缩短输入。",
                "technical_analysis": "结构化解析失败。",
                "financial_health": "结构化解析失败。",
                "multi_lens": "结构化解析失败。",
            })
        return report_data

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
