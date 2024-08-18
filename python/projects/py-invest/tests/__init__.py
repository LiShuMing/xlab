"""Tests for specialist agents."""

import pytest
from agents.specialist_agents import (
    TechnicalOutput,
    FundamentalOutput,
    RiskOutput,
    SectorOutput,
    RiskItem,
    ComparableCompany,
    Catalyst,
)


class TestTechnicalOutput:
    """Tests for TechnicalOutput dataclass."""

    def test_default_values(self):
        """Test default values are set correctly."""
        output = TechnicalOutput()
        assert output.trend == "sideways"
        assert output.support is None
        assert output.resistance is None
        assert output.momentum_score == 5
        assert output.pattern == "no clear pattern"
        assert output.near_term_outlook == ""

    def test_custom_values(self):
        """Test custom values are set correctly."""
        output = TechnicalOutput(
            trend="bullish",
            support=100.0,
            resistance=120.0,
            momentum_score=8,
            pattern="ascending triangle",
            near_term_outlook="Bullish momentum building",
        )
        assert output.trend == "bullish"
        assert output.support == 100.0
        assert output.resistance == 120.0
        assert output.momentum_score == 8
        assert output.pattern == "ascending triangle"


class TestFundamentalOutput:
    """Tests for FundamentalOutput dataclass."""

    def test_default_values(self):
        """Test default values are set correctly."""
        output = FundamentalOutput()
        assert output.pe_ratio is None
        assert output.valuation == "fairly valued"
        assert output.quality_score == 5
        assert output.sector_avg_pe_source == "llm_estimate"

    def test_custom_values(self):
        """Test custom values are set correctly."""
        output = FundamentalOutput(
            pe_ratio=25.5,
            pb_ratio=3.2,
            valuation="undervalued",
            quality_score=8,
        )
        assert output.pe_ratio == 25.5
        assert output.pb_ratio == 3.2
        assert output.valuation == "undervalued"
        assert output.quality_score == 8


class TestRiskOutput:
    """Tests for RiskOutput dataclass."""

    def test_default_values(self):
        """Test default values are set correctly."""
        output = RiskOutput()
        assert output.risks == []
        assert output.hedge_suggestion == "none"

    def test_with_risks(self):
        """Test with risk items."""
        risks = [
            RiskItem(description="Market volatility", probability="high", impact="medium"),
            RiskItem(description="Regulatory risk", probability="low", impact="high"),
        ]
        output = RiskOutput(risks=risks, hedge_suggestion="Diversification")
        assert len(output.risks) == 2
        assert output.hedge_suggestion == "Diversification"


class TestSectorOutput:
    """Tests for SectorOutput dataclass."""

    def test_default_values(self):
        """Test default values are set correctly."""
        output = SectorOutput()
        assert output.sector == ""
        assert output.positioning == "leader"
        assert output.comps == []
        assert output.catalysts == []

    def test_with_comps(self):
        """Test with comparable companies."""
        comps = [
            ComparableCompany(name="Company A", code="CMPA", pe=20.0, relative_val="cheaper"),
        ]
        output = SectorOutput(sector="Technology", comps=comps)
        assert output.sector == "Technology"
        assert len(output.comps) == 1


class TestCatalyst:
    """Tests for Catalyst dataclass."""

    def test_default_values(self):
        """Test default values are set correctly."""
        catalyst = Catalyst()
        assert catalyst.event == ""
        assert catalyst.timing == ""
        assert catalyst.impact == "neutral"

    def test_custom_values(self):
        """Test custom values are set correctly."""
        catalyst = Catalyst(
            event="Q1 Earnings",
            timing="2026-04",
            impact="positive",
        )
        assert catalyst.event == "Q1 Earnings"
        assert catalyst.timing == "2026-04"
        assert catalyst.impact == "positive"


class TestRiskItem:
    """Tests for RiskItem dataclass."""

    def test_default_values(self):
        """Test default values are set correctly."""
        item = RiskItem()
        assert item.description == ""
        assert item.probability == "medium"
        assert item.impact == "medium"


class TestComparableCompany:
    """Tests for ComparableCompany dataclass."""

    def test_default_values(self):
        """Test default values are set correctly."""
        comp = ComparableCompany()
        assert comp.name == ""
        assert comp.code == ""
        assert comp.pe is None
        assert comp.relative_val == "fairly valued"