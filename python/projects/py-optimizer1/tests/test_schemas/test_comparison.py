"""Tests for comparison schemas."""

from datetime import datetime

from optimizer_analysis.schemas.comparison import (
    ComparisonCell,
    ComparisonDimension,
    ComparisonMatrix,
    ComparisonReport,
)
from optimizer_analysis.schemas.base import Evidence, EvidenceType


def test_comparison_dimension_values():
    """All comparison dimensions should be available."""
    dimensions = [
        ComparisonDimension.LIFECYCLE,
        ComparisonDimension.RULE_COVERAGE,
        ComparisonDimension.PROPERTY_SYSTEM,
        ComparisonDimension.STATS_COST,
        ComparisonDimension.OBSERVABILITY,
        ComparisonDimension.EXTENSIBILITY,
    ]
    assert len(dimensions) == 6
    assert ComparisonDimension.LIFECYCLE.value == "lifecycle"
    assert ComparisonDimension.RULE_COVERAGE.value == "rule_coverage"
    assert ComparisonDimension.PROPERTY_SYSTEM.value == "property_system"
    assert ComparisonDimension.STATS_COST.value == "stats_cost"
    assert ComparisonDimension.OBSERVABILITY.value == "observability"
    assert ComparisonDimension.EXTENSIBILITY.value == "extensibility"


def test_comparison_cell_creation():
    """ComparisonCell must have engine, dimension, and value."""
    cell = ComparisonCell(
        engine="StarRocks",
        dimension=ComparisonDimension.LIFECYCLE,
        value="yes",
        details="Full Cascades-style lifecycle",
        evidence=[
            Evidence(
                file_path="src/optimizer/optimizer.cpp",
                description="Main optimizer entry point",
                evidence_type=EvidenceType.SOURCE_CODE
            )
        ]
    )
    assert cell.engine == "StarRocks"
    assert cell.dimension == ComparisonDimension.LIFECYCLE
    assert cell.value == "yes"
    assert cell.details == "Full Cascades-style lifecycle"
    assert len(cell.evidence) == 1


def test_comparison_cell_minimal():
    """ComparisonCell with minimal required fields."""
    cell = ComparisonCell(
        engine="PostgreSQL",
        dimension=ComparisonDimension.RULE_COVERAGE,
        value="partial"
    )
    assert cell.engine == "PostgreSQL"
    assert cell.dimension == ComparisonDimension.RULE_COVERAGE
    assert cell.value == "partial"
    assert cell.details is None
    assert cell.evidence == []


def test_comparison_matrix_creation():
    """ComparisonMatrix must have engines and dimensions."""
    matrix = ComparisonMatrix(
        engines=["StarRocks", "PostgreSQL"],
        dimensions=[
            ComparisonDimension.LIFECYCLE,
            ComparisonDimension.RULE_COVERAGE,
        ],
        cells=[
            ComparisonCell(
                engine="StarRocks",
                dimension=ComparisonDimension.LIFECYCLE,
                value="yes"
            ),
            ComparisonCell(
                engine="PostgreSQL",
                dimension=ComparisonDimension.LIFECYCLE,
                value="partial"
            ),
        ]
    )
    assert len(matrix.engines) == 2
    assert len(matrix.dimensions) == 2
    assert len(matrix.cells) == 2
    assert isinstance(matrix.generated_at, datetime)


def test_comparison_matrix_default_cells():
    """ComparisonMatrix can be created without cells."""
    matrix = ComparisonMatrix(
        engines=["StarRocks"],
        dimensions=[ComparisonDimension.LIFECYCLE]
    )
    assert matrix.cells == []
    assert isinstance(matrix.generated_at, datetime)


def test_comparison_report_creation():
    """ComparisonReport must have title and engines_compared."""
    report = ComparisonReport(
        title="Optimizer Comparison: StarRocks vs PostgreSQL",
        engines_compared=["StarRocks", "PostgreSQL"],
        matrices=[
            ComparisonMatrix(
                engines=["StarRocks", "PostgreSQL"],
                dimensions=[ComparisonDimension.LIFECYCLE]
            )
        ],
        findings=[
            "StarRocks has more complete Cascades implementation",
            "PostgreSQL uses planner-based approach"
        ],
        recommendations=[
            "Consider StarRocks for complex query optimization",
            "PostgreSQL better for simple OLTP workloads"
        ]
    )
    assert report.title == "Optimizer Comparison: StarRocks vs PostgreSQL"
    assert len(report.engines_compared) == 2
    assert len(report.matrices) == 1
    assert len(report.findings) == 2
    assert len(report.recommendations) == 2
    assert isinstance(report.generated_at, datetime)


def test_comparison_report_minimal():
    """ComparisonReport with minimal required fields."""
    report = ComparisonReport(
        title="Minimal Report",
        engines_compared=["Engine1"]
    )
    assert report.title == "Minimal Report"
    assert report.engines_compared == ["Engine1"]
    assert report.matrices == []
    assert report.findings == []
    assert report.recommendations == []
    assert isinstance(report.generated_at, datetime)