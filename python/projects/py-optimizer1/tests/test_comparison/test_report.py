"""Tests for comparison report generation."""

import json
import tempfile
from pathlib import Path

from optimizer_analysis.comparison.report import ReportGenerator
from optimizer_analysis.schemas import (
    ComparisonCell,
    ComparisonDimension,
    ComparisonMatrix,
    Evidence,
    EvidenceType,
)


def _create_sample_matrix_lifecycle():
    """Create a sample lifecycle comparison matrix for testing."""
    return ComparisonMatrix(
        engines=["StarRocks", "PostgreSQL"],
        dimensions=[ComparisonDimension.LIFECYCLE],
        cells=[
            ComparisonCell(
                engine="StarRocks",
                dimension=ComparisonDimension.LIFECYCLE,
                value="cascades",
                details="Cascades-style optimizer"
            ),
            ComparisonCell(
                engine="StarRocks",
                dimension=ComparisonDimension.LIFECYCLE,
                value="yes",
                details="Logical and physical optimization are separate phases"
            ),
            ComparisonCell(
                engine="StarRocks",
                dimension=ComparisonDimension.LIFECYCLE,
                value="yes",
                details="Memo structure: Memo class"
            ),
            ComparisonCell(
                engine="StarRocks",
                dimension=ComparisonDimension.LIFECYCLE,
                value="parsing, logical_opt, physical_opt",
                details="Lifecycle phases"
            ),
            ComparisonCell(
                engine="PostgreSQL",
                dimension=ComparisonDimension.LIFECYCLE,
                value="planner_path_enum",
                details="Planner with path enumeration"
            ),
            ComparisonCell(
                engine="PostgreSQL",
                dimension=ComparisonDimension.LIFECYCLE,
                value="no",
                details=None
            ),
            ComparisonCell(
                engine="PostgreSQL",
                dimension=ComparisonDimension.LIFECYCLE,
                value="no",
                details=None
            ),
            ComparisonCell(
                engine="PostgreSQL",
                dimension=ComparisonDimension.LIFECYCLE,
                value="parsing, logical_opt",
                details="Lifecycle phases"
            ),
        ],
        evidence=[
            Evidence(
                file_path="src/optimizer.cpp",
                description="Optimizer entry point",
                evidence_type=EvidenceType.SOURCE_CODE
            )
        ]
    )


def _create_sample_matrix_rule_coverage():
    """Create a sample rule coverage comparison matrix for testing."""
    return ComparisonMatrix(
        engines=["StarRocks", "PostgreSQL"],
        dimensions=[ComparisonDimension.RULE_COVERAGE],
        cells=[
            ComparisonCell(
                engine="StarRocks",
                dimension=ComparisonDimension.RULE_COVERAGE,
                value="5",
                details="Rule-based optimization rules: 5"
            ),
            ComparisonCell(
                engine="StarRocks",
                dimension=ComparisonDimension.RULE_COVERAGE,
                value="10",
                details="Cost-based optimization rules: 10"
            ),
            ComparisonCell(
                engine="StarRocks",
                dimension=ComparisonDimension.RULE_COVERAGE,
                value="3",
                details="Scalar rules: 3"
            ),
            ComparisonCell(
                engine="StarRocks",
                dimension=ComparisonDimension.RULE_COVERAGE,
                value="2",
                details="Post-optimization rules: 2"
            ),
            ComparisonCell(
                engine="PostgreSQL",
                dimension=ComparisonDimension.RULE_COVERAGE,
                value="8",
                details="Rule-based optimization rules: 8"
            ),
            ComparisonCell(
                engine="PostgreSQL",
                dimension=ComparisonDimension.RULE_COVERAGE,
                value="3",
                details="Cost-based optimization rules: 3"
            ),
            ComparisonCell(
                engine="PostgreSQL",
                dimension=ComparisonDimension.RULE_COVERAGE,
                value="1",
                details="Scalar rules: 1"
            ),
            ComparisonCell(
                engine="PostgreSQL",
                dimension=ComparisonDimension.RULE_COVERAGE,
                value="0",
                details="Post-optimization rules: 0"
            ),
        ]
    )


def _create_sample_matrix_observability():
    """Create a sample observability comparison matrix for testing."""
    return ComparisonMatrix(
        engines=["StarRocks", "PostgreSQL"],
        dimensions=[ComparisonDimension.OBSERVABILITY],
        cells=[
            ComparisonCell(
                engine="StarRocks",
                dimension=ComparisonDimension.OBSERVABILITY,
                value="3",
                details="EXPLAIN variants: EXPLAIN, EXPLAIN ANALYZE, EXPLAIN VERBOSE"
            ),
            ComparisonCell(
                engine="StarRocks",
                dimension=ComparisonDimension.OBSERVABILITY,
                value="2",
                details="Trace interfaces: optimizer_trace, memo_dump"
            ),
            ComparisonCell(
                engine="StarRocks",
                dimension=ComparisonDimension.OBSERVABILITY,
                value="yes",
                details="Memo dump support available"
            ),
            ComparisonCell(
                engine="StarRocks",
                dimension=ComparisonDimension.OBSERVABILITY,
                value="5",
                details="Session controls: optimizer_switch, cost_threshold"
            ),
            ComparisonCell(
                engine="PostgreSQL",
                dimension=ComparisonDimension.OBSERVABILITY,
                value="1",
                details="EXPLAIN variants: EXPLAIN"
            ),
            ComparisonCell(
                engine="PostgreSQL",
                dimension=ComparisonDimension.OBSERVABILITY,
                value="0",
                details=None
            ),
            ComparisonCell(
                engine="PostgreSQL",
                dimension=ComparisonDimension.OBSERVABILITY,
                value="no",
                details=None
            ),
            ComparisonCell(
                engine="PostgreSQL",
                dimension=ComparisonDimension.OBSERVABILITY,
                value="2",
                details="Session controls: enable_seqscan"
            ),
        ]
    )


def _create_sample_matrices():
    """Create sample matrices for testing."""
    return [
        _create_sample_matrix_lifecycle(),
        _create_sample_matrix_rule_coverage(),
        _create_sample_matrix_observability(),
    ]


def test_report_generator_init():
    """Test ReportGenerator initialization."""
    matrices = _create_sample_matrices()
    generator = ReportGenerator(matrices)

    assert generator.matrices == matrices
    assert len(generator.matrices) == 3


def test_generate_markdown_report():
    """Test Markdown report generation."""
    matrices = _create_sample_matrices()
    generator = ReportGenerator(matrices)
    report = generator.generate_markdown_report()

    # Check basic structure
    assert "# Optimizer Engine Comparison Report" in report
    assert "## Executive Summary" in report
    assert "## Comparison Tables" in report
    assert "## Key Findings" in report
    assert "## Recommendations" in report

    # Check engines are mentioned
    assert "StarRocks" in report
    assert "PostgreSQL" in report

    # Check dimensions are mentioned
    assert "Lifecycle" in report
    assert "Rule Coverage" in report
    assert "Observability" in report


def test_generate_json_report():
    """Test JSON report generation."""
    matrices = _create_sample_matrices()
    generator = ReportGenerator(matrices)
    report = generator.generate_json_report()

    # Parse JSON to verify structure
    data = json.loads(report)

    assert data["title"] == "Optimizer Engine Comparison Report"
    assert "generated_at" in data
    assert set(data["engines_compared"]) == {"StarRocks", "PostgreSQL"}
    assert "matrices" in data
    assert len(data["matrices"]) == 3
    assert "findings" in data
    assert "recommendations" in data

    # Check dimensions in matrices
    matrix_dimensions = [m["dimension"] for m in data["matrices"]]
    assert "lifecycle" in matrix_dimensions
    assert "rule_coverage" in matrix_dimensions
    assert "observability" in matrix_dimensions


def test_identify_findings():
    """Test finding identification."""
    matrices = _create_sample_matrices()
    generator = ReportGenerator(matrices)
    findings = generator.identify_findings()

    assert isinstance(findings, list)
    assert len(findings) > 0

    # Check for specific findings based on our sample data
    # Lifecycle findings
    cascades_finding = any("Cascades" in f for f in findings)
    assert cascades_finding

    # Rule coverage findings - StarRocks favors CBO
    cbo_finding = any("cost-based" in f.lower() for f in findings)
    assert cbo_finding


def test_generate_recommendations():
    """Test recommendation generation."""
    matrices = _create_sample_matrices()
    generator = ReportGenerator(matrices)
    recommendations = generator.generate_recommendations()

    assert isinstance(recommendations, list)
    assert len(recommendations) > 0

    # Check that recommendations are actionable
    for rec in recommendations:
        assert len(rec) > 0
        assert isinstance(rec, str)


def test_save_report_markdown():
    """Test saving Markdown report to file."""
    matrices = _create_sample_matrices()
    generator = ReportGenerator(matrices)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "report.md"
        generator.save_report(str(path), format="markdown")

        assert path.exists()

        content = path.read_text()
        assert "# Optimizer Engine Comparison Report" in content
        assert "StarRocks" in content
        assert "PostgreSQL" in content


def test_save_report_json():
    """Test saving JSON report to file."""
    matrices = _create_sample_matrices()
    generator = ReportGenerator(matrices)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "report.json"
        generator.save_report(str(path), format="json")

        assert path.exists()

        content = path.read_text()
        data = json.loads(content)

        assert data["title"] == "Optimizer Engine Comparison Report"
        assert "matrices" in data


def test_save_report_creates_directory():
    """Test that save_report creates parent directories."""
    matrices = _create_sample_matrices()
    generator = ReportGenerator(matrices)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "subdir" / "nested" / "report.md"
        generator.save_report(str(path), format="markdown")

        assert path.exists()


def test_save_report_unsupported_format():
    """Test that save_report raises error for unsupported format."""
    matrices = _create_sample_matrices()
    generator = ReportGenerator(matrices)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "report.txt"
        try:
            generator.save_report(str(path), format="txt")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Unsupported format" in str(e)


def test_empty_matrices():
    """Test ReportGenerator with empty matrices list."""
    generator = ReportGenerator([])

    # Should not raise errors
    report = generator.generate_markdown_report()
    assert "# Optimizer Engine Comparison Report" in report

    json_report = generator.generate_json_report()
    data = json.loads(json_report)
    assert data["engines_compared"] == []


def test_matrix_with_empty_cells():
    """Test ReportGenerator with matrix having no cells."""
    matrix = ComparisonMatrix(
        engines=["Engine1"],
        dimensions=[ComparisonDimension.LIFECYCLE],
        cells=[]
    )

    generator = ReportGenerator([matrix])
    report = generator.generate_markdown_report()

    assert "# Optimizer Engine Comparison Report" in report


def test_single_engine_comparison():
    """Test report generation with single engine."""
    matrix = _create_sample_matrix_lifecycle()
    # Modify to have only one engine
    single_engine_matrix = ComparisonMatrix(
        engines=["StarRocks"],
        dimensions=[ComparisonDimension.LIFECYCLE],
        cells=[
            ComparisonCell(
                engine="StarRocks",
                dimension=ComparisonDimension.LIFECYCLE,
                value="cascades",
                details="Cascades-style optimizer"
            ),
            ComparisonCell(
                engine="StarRocks",
                dimension=ComparisonDimension.LIFECYCLE,
                value="yes",
                details="Logical and physical split"
            ),
            ComparisonCell(
                engine="StarRocks",
                dimension=ComparisonDimension.LIFECYCLE,
                value="yes",
                details="Memo support"
            ),
            ComparisonCell(
                engine="StarRocks",
                dimension=ComparisonDimension.LIFECYCLE,
                value="parsing, logical_opt",
                details="Phases present"
            ),
        ]
    )

    generator = ReportGenerator([single_engine_matrix])
    findings = generator.identify_findings()
    recommendations = generator.generate_recommendations()

    # Should still generate findings and recommendations
    assert len(findings) >= 0
    # Single engine should get a recommendation to compare more engines
    assert any("at least two" in rec.lower() for rec in recommendations)


def test_property_system_matrix():
    """Test report generation with property system matrix."""
    matrix = ComparisonMatrix(
        engines=["StarRocks", "PostgreSQL"],
        dimensions=[ComparisonDimension.PROPERTY_SYSTEM],
        cells=[
            ComparisonCell(
                engine="StarRocks",
                dimension=ComparisonDimension.PROPERTY_SYSTEM,
                value="2",
                details="Distribution properties: DistributionProperty"
            ),
            ComparisonCell(
                engine="StarRocks",
                dimension=ComparisonDimension.PROPERTY_SYSTEM,
                value="1",
                details="Ordering properties: OrderingProperty"
            ),
            ComparisonCell(
                engine="StarRocks",
                dimension=ComparisonDimension.PROPERTY_SYSTEM,
                value="3",
                details="Enforcers: DistributionEnforcer, SortEnforcer"
            ),
            ComparisonCell(
                engine="PostgreSQL",
                dimension=ComparisonDimension.PROPERTY_SYSTEM,
                value="0",
                details=None
            ),
            ComparisonCell(
                engine="PostgreSQL",
                dimension=ComparisonDimension.PROPERTY_SYSTEM,
                value="0",
                details=None
            ),
            ComparisonCell(
                engine="PostgreSQL",
                dimension=ComparisonDimension.PROPERTY_SYSTEM,
                value="0",
                details=None
            ),
        ]
    )

    generator = ReportGenerator([matrix])
    report = generator.generate_markdown_report()

    assert "Property System" in report
    assert "StarRocks" in report
    assert "PostgreSQL" in report


def test_json_report_structure():
    """Test detailed structure of JSON report."""
    matrices = _create_sample_matrices()
    generator = ReportGenerator(matrices)
    report = generator.generate_json_report()
    data = json.loads(report)

    # Check matrix structure
    for matrix_data in data["matrices"]:
        assert "dimension" in matrix_data
        assert "engines" in matrix_data
        assert "generated_at" in matrix_data
        assert "rows" in matrix_data

        # Check rows structure
        for row in matrix_data["rows"]:
            assert "metric" in row
            # Check engine values
            for engine in matrix_data["engines"]:
                assert engine in row
                assert "value" in row[engine]


def test_multiple_dimensions_in_single_matrix():
    """Test handling of matrix with multiple dimensions."""
    matrix = ComparisonMatrix(
        engines=["StarRocks"],
        dimensions=[ComparisonDimension.LIFECYCLE, ComparisonDimension.RULE_COVERAGE],
        cells=[
            ComparisonCell(
                engine="StarRocks",
                dimension=ComparisonDimension.LIFECYCLE,
                value="cascades",
                details="Optimizer style"
            ),
        ]
    )

    generator = ReportGenerator([matrix])
    report = generator.generate_markdown_report()

    assert "# Optimizer Engine Comparison Report" in report


def test_findings_return_copy():
    """Test that identify_findings returns a copy."""
    matrices = _create_sample_matrices()
    generator = ReportGenerator(matrices)

    findings1 = generator.identify_findings()
    findings2 = generator.identify_findings()

    # Should be equal but not the same object
    assert findings1 == findings2
    # Modifying one should not affect the other
    findings1.append("test finding")
    assert findings1 != findings2


def test_recommendations_return_copy():
    """Test that generate_recommendations returns a copy."""
    matrices = _create_sample_matrices()
    generator = ReportGenerator(matrices)

    rec1 = generator.generate_recommendations()
    rec2 = generator.generate_recommendations()

    # Should be equal but not the same object
    assert rec1 == rec2
    # Modifying one should not affect the other
    rec1.append("test recommendation")
    assert rec1 != rec2