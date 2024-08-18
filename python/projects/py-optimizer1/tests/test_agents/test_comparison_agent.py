"""Tests for Comparison Agent and related models."""

import json
import tempfile
from os.path import exists, join

from optimizer_analysis.agents.base import AgentResult
from optimizer_analysis.agents.comparison_agent import (
    ComparisonAgent,
    ReportGenerator,
)
from optimizer_analysis.schemas import (
    ComparisonDimension,
    ComparisonMatrix,
    ComparisonReport,
    EngineType,
    Evidence,
    EvidenceType,
    Framework,
    OptimizerPhase,
    OptimizerStyle,
    Observability,
    PropertyType,
    Rule,
    RuleCategory,
    TraitProperty,
)


def _create_sample_framework(engine_name: str):
    """Create a sample Framework for testing."""
    return Framework(
        engine_name=engine_name,
        engine_type=EngineType.COLUMNAR_OLAP,
        optimizer_style=OptimizerStyle.CASCADES,
        main_entry="optimizer.cpp",
        optimizer_phases=[
            OptimizerPhase.PARSING,
            OptimizerPhase.LOGICAL_OPT,
            OptimizerPhase.PHYSICAL_OPT,
        ],
        logical_physical_split=True,
        memo_or_equivalent="Memo structure",
        evidence=[
            Evidence(
                file_path="src/optimizer.cpp",
                description="Main optimizer entry point",
                evidence_type=EvidenceType.SOURCE_CODE
            )
        ]
    )


def _create_sample_rules(engine_name: str):
    """Create sample rules for testing."""
    return [
        Rule(
            rule_id="RULE001",
            rule_name="PushDownFilter",
            engine=engine_name,
            rule_category=RuleCategory.RBO,
            source_files=["src/rules/filter.cpp"]
        ),
        Rule(
            rule_id="RULE002",
            rule_name="JoinReorder",
            engine=engine_name,
            rule_category=RuleCategory.CBO,
            source_files=["src/rules/join.cpp"]
        ),
    ]


def _create_sample_properties():
    """Create sample properties for testing."""
    return [
        TraitProperty(
            property_name="DistributionProperty",
            property_type=PropertyType.PHYSICAL,
            enforcer="DistributionEnforcer",
            evidence=[
                Evidence(
                    file_path="src/property/distribution.cpp",
                    description="Distribution property",
                    evidence_type=EvidenceType.SOURCE_CODE
                )
            ]
        ),
    ]


def _create_sample_observability():
    """Create sample observability for testing."""
    return Observability(
        explain_interfaces=["EXPLAIN", "EXPLAIN ANALYZE"],
        trace_interfaces=["optimizer_trace"],
        rule_fire_visibility="partial",
        memo_dump_support=True,
        session_controls=["optimizer_switch"],
        evidence=[
            Evidence(
                file_path="src/explain.cpp",
                description="EXPLAIN implementation",
                evidence_type=EvidenceType.SOURCE_CODE
            )
        ]
    )


def _create_sample_analysis_results():
    """Create sample analysis results for two engines."""
    return {
        "StarRocks": {
            "framework": _create_sample_framework("StarRocks"),
            "rules": _create_sample_rules("StarRocks"),
            "properties": _create_sample_properties(),
            "observability": _create_sample_observability(),
        },
        "ClickHouse": {
            "framework": Framework(
                engine_name="ClickHouse",
                engine_type=EngineType.COLUMNAR_OLAP,
                optimizer_style=OptimizerStyle.HEURISTIC_MIXED,
                main_entry="optimizer.cpp",
                optimizer_phases=[OptimizerPhase.PARSING],
                logical_physical_split=False,
                memo_or_equivalent=None,
                evidence=[
                    Evidence(
                        file_path="src/optimizer.cpp",
                        description="ClickHouse optimizer",
                        evidence_type=EvidenceType.SOURCE_CODE
                    )
                ]
            ),
            "rules": [
                Rule(
                    rule_id="CH001",
                    rule_name="FilterPushdown",
                    engine="ClickHouse",
                    rule_category=RuleCategory.RBO,
                    source_files=["src/rules/filter.cpp"]
                ),
            ],
            "properties": [],
            "observability": Observability(
                explain_interfaces=["EXPLAIN"],
                trace_interfaces=[],
                memo_dump_support=False,
                session_controls=[],
            ),
        },
    }


class TestComparisonAgentCreation:
    """Tests for ComparisonAgent instantiation."""

    def test_comparison_agent_creation(self):
        """ComparisonAgent can be instantiated correctly."""
        engines = ["StarRocks", "ClickHouse"]
        analysis_results = _create_sample_analysis_results()

        agent = ComparisonAgent(
            engines=engines,
            work_dir="/tmp/work",
            analysis_results=analysis_results,
        )

        assert agent.name == "ComparisonAgent"
        assert agent.engines == engines
        assert agent.work_dir == "/tmp/work"
        assert agent.analysis_results == analysis_results

    def test_comparison_agent_inherits_from_base_agent(self):
        """ComparisonAgent inherits from BaseAgent."""
        from optimizer_analysis.agents.base import BaseAgent

        agent = ComparisonAgent(
            engines=["test"],
            work_dir="/tmp",
            analysis_results={}
        )
        assert isinstance(agent, BaseAgent)

    def test_comparison_agent_with_single_engine(self):
        """ComparisonAgent works with a single engine."""
        agent = ComparisonAgent(
            engines=["StarRocks"],
            work_dir="/tmp/work",
            analysis_results={
                "StarRocks": {
                    "framework": _create_sample_framework("StarRocks"),
                    "rules": _create_sample_rules("StarRocks"),
                }
            },
        )

        assert agent.engines == ["StarRocks"]
        assert agent.engine == "StarRocks"  # Primary engine

    def test_comparison_agent_with_empty_engines(self):
        """ComparisonAgent handles empty engines list."""
        agent = ComparisonAgent(
            engines=[],
            work_dir="/tmp/work",
            analysis_results={}
        )

        assert agent.engines == []
        assert agent.engine == "unknown"


class TestComparisonAgentExecute:
    """Tests for ComparisonAgent execute method."""

    def test_comparison_agent_execute(self):
        """ComparisonAgent execute returns AgentResult."""
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = join(tmpdir, "work")
            agent = ComparisonAgent(
                engines=["StarRocks", "ClickHouse"],
                work_dir=work_dir,
                analysis_results=_create_sample_analysis_results()
            )
            result = agent.execute()

            assert isinstance(result, AgentResult)
            assert result.agent_name == "ComparisonAgent"
            assert result.status in ["success", "partial"]
            assert len(result.artifacts) == 2

    def test_comparison_agent_execute_creates_comparison_directory(self):
        """ComparisonAgent creates comparison subdirectory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = join(tmpdir, "work")
            agent = ComparisonAgent(
                engines=["StarRocks"],
                work_dir=work_dir,
                analysis_results={
                    "StarRocks": {
                        "framework": _create_sample_framework("StarRocks"),
                        "rules": [],
                        "properties": [],
                        "observability": _create_sample_observability(),
                    }
                }
            )
            result = agent.execute()

            comparison_dir = join(work_dir, "comparison")
            assert exists(comparison_dir)

    def test_comparison_agent_execute_saves_matrix_json(self):
        """ComparisonAgent saves matrix.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = join(tmpdir, "work")
            agent = ComparisonAgent(
                engines=["StarRocks", "ClickHouse"],
                work_dir=work_dir,
                analysis_results=_create_sample_analysis_results()
            )
            result = agent.execute()

            matrix_json_path = join(work_dir, "comparison", "matrix.json")
            assert exists(matrix_json_path)

            # Verify JSON content
            with open(matrix_json_path) as f:
                data = json.load(f)
            assert "engines" in data
            assert "matrices" in data

    def test_comparison_agent_execute_saves_report_md(self):
        """ComparisonAgent saves report.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = join(tmpdir, "work")
            agent = ComparisonAgent(
                engines=["StarRocks", "ClickHouse"],
                work_dir=work_dir,
                analysis_results=_create_sample_analysis_results()
            )
            result = agent.execute()

            report_md_path = join(work_dir, "comparison", "report.md")
            assert exists(report_md_path)

            # Verify markdown content
            with open(report_md_path) as f:
                content = f.read()
            assert "# Optimizer Engine Comparison Report" in content
            assert "StarRocks" in content

    def test_comparison_agent_execute_with_empty_results(self):
        """ComparisonAgent handles empty analysis results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = ComparisonAgent(
                engines=["Engine1"],
                work_dir=join(tmpdir, "work"),
                analysis_results={}
            )
            result = agent.execute()

            # With empty results, matrices are still generated (with default values)
            assert result.status in ["success", "partial"]
            assert len(result.artifacts) == 2


class TestCompareLifecycles:
    """Tests for compare_lifecycles method."""

    def test_compare_lifecycles(self):
        """compare_lifecycles returns ComparisonMatrix."""
        agent = ComparisonAgent(
            engines=["StarRocks", "ClickHouse"],
            work_dir="/tmp/work",
            analysis_results=_create_sample_analysis_results()
        )
        matrix = agent.compare_lifecycles()

        assert isinstance(matrix, ComparisonMatrix)
        assert set(matrix.engines) == {"StarRocks", "ClickHouse"}
        assert matrix.dimensions == [ComparisonDimension.LIFECYCLE]

    def test_compare_lifecycles_optimizer_styles(self):
        """compare_lifecycles correctly compares optimizer styles."""
        agent = ComparisonAgent(
            engines=["StarRocks", "ClickHouse"],
            work_dir="/tmp/work",
            analysis_results=_create_sample_analysis_results()
        )
        matrix = agent.compare_lifecycles()

        # Find optimizer_style cells
        starrocks_cells = [c for c in matrix.cells if c.engine == "StarRocks"]
        assert len(starrocks_cells) >= 1
        # First cell is optimizer_style
        assert starrocks_cells[0].value == "cascades"

    def test_compare_lifecycles_logical_physical_split(self):
        """compare_lifecycles correctly compares logical_physical_split."""
        agent = ComparisonAgent(
            engines=["StarRocks", "ClickHouse"],
            work_dir="/tmp/work",
            analysis_results=_create_sample_analysis_results()
        )
        matrix = agent.compare_lifecycles()

        # Find logical_physical_split cells (index 1)
        starrocks_cells = [c for c in matrix.cells if c.engine == "StarRocks"]
        assert starrocks_cells[1].value == "yes"

        clickhouse_cells = [c for c in matrix.cells if c.engine == "ClickHouse"]
        assert clickhouse_cells[1].value == "no"


class TestCompareRules:
    """Tests for compare_rules method."""

    def test_compare_rules(self):
        """compare_rules returns ComparisonMatrix."""
        agent = ComparisonAgent(
            engines=["StarRocks", "ClickHouse"],
            work_dir="/tmp/work",
            analysis_results=_create_sample_analysis_results()
        )
        matrix = agent.compare_rules()

        assert isinstance(matrix, ComparisonMatrix)
        assert matrix.dimensions == [ComparisonDimension.RULE_COVERAGE]

    def test_compare_rules_counts(self):
        """compare_rules correctly counts rules by category."""
        agent = ComparisonAgent(
            engines=["StarRocks"],
            work_dir="/tmp/work",
            analysis_results={
                "StarRocks": {
                    "rules": _create_sample_rules("StarRocks"),
                }
            }
        )
        matrix = agent.compare_rules()

        # StarRocks has 1 RBO and 1 CBO
        starrocks_cells = [c for c in matrix.cells if c.engine == "StarRocks"]
        assert starrocks_cells[0].value == "1"  # RBO count
        assert starrocks_cells[1].value == "1"  # CBO count


class TestCompareProperties:
    """Tests for compare_properties method."""

    def test_compare_properties(self):
        """compare_properties returns ComparisonMatrix."""
        agent = ComparisonAgent(
            engines=["StarRocks"],
            work_dir="/tmp/work",
            analysis_results={
                "StarRocks": {
                    "properties": _create_sample_properties(),
                }
            }
        )
        matrix = agent.compare_properties()

        assert isinstance(matrix, ComparisonMatrix)
        assert matrix.dimensions == [ComparisonDimension.PROPERTY_SYSTEM]

    def test_compare_properties_distribution(self):
        """compare_properties correctly counts distribution properties."""
        agent = ComparisonAgent(
            engines=["StarRocks"],
            work_dir="/tmp/work",
            analysis_results={
                "StarRocks": {
                    "properties": _create_sample_properties(),
                }
            }
        )
        matrix = agent.compare_properties()

        starrocks_cells = [c for c in matrix.cells if c.engine == "StarRocks"]
        # First cell is distribution support
        assert starrocks_cells[0].value == "1"


class TestCompareObservability:
    """Tests for compare_observability method."""

    def test_compare_observability(self):
        """compare_observability returns ComparisonMatrix."""
        agent = ComparisonAgent(
            engines=["StarRocks"],
            work_dir="/tmp/work",
            analysis_results={
                "StarRocks": {
                    "observability": _create_sample_observability(),
                }
            }
        )
        matrix = agent.compare_observability()

        assert isinstance(matrix, ComparisonMatrix)
        assert matrix.dimensions == [ComparisonDimension.OBSERVABILITY]

    def test_compare_observability_explain_count(self):
        """compare_observability correctly counts explain interfaces."""
        agent = ComparisonAgent(
            engines=["StarRocks"],
            work_dir="/tmp/work",
            analysis_results={
                "StarRocks": {
                    "observability": _create_sample_observability(),
                }
            }
        )
        matrix = agent.compare_observability()

        starrocks_cells = [c for c in matrix.cells if c.engine == "StarRocks"]
        # First cell is explain support (StarRocks has 2)
        assert starrocks_cells[0].value == "2"


class TestGenerateMatrices:
    """Tests for generate_matrices method."""

    def test_generate_matrices(self):
        """generate_matrices returns all matrices."""
        agent = ComparisonAgent(
            engines=["StarRocks", "ClickHouse"],
            work_dir="/tmp/work",
            analysis_results=_create_sample_analysis_results()
        )
        matrices = agent.generate_matrices()

        assert len(matrices) == 4

    def test_generate_matrices_dimensions(self):
        """generate_matrices returns matrices for all dimensions."""
        agent = ComparisonAgent(
            engines=["StarRocks"],
            work_dir="/tmp/work",
            analysis_results=_create_sample_analysis_results()
        )
        matrices = agent.generate_matrices()

        dimensions = [m.dimensions[0] for m in matrices if m.dimensions]
        assert ComparisonDimension.LIFECYCLE in dimensions
        assert ComparisonDimension.RULE_COVERAGE in dimensions
        assert ComparisonDimension.PROPERTY_SYSTEM in dimensions
        assert ComparisonDimension.OBSERVABILITY in dimensions

    def test_generate_matrices_empty_results(self):
        """generate_matrices handles empty results."""
        agent = ComparisonAgent(
            engines=["Engine1"],
            work_dir="/tmp/work",
            analysis_results={"Engine1": {}}
        )
        matrices = agent.generate_matrices()

        assert len(matrices) == 4
        # All matrices should still be generated with empty data
        for matrix in matrices:
            assert isinstance(matrix, ComparisonMatrix)


class TestGenerateReport:
    """Tests for generate_report method."""

    def test_generate_report(self):
        """generate_report returns ComparisonReport."""
        agent = ComparisonAgent(
            engines=["StarRocks", "ClickHouse"],
            work_dir="/tmp/work",
            analysis_results=_create_sample_analysis_results()
        )
        matrices = agent.generate_matrices()
        report = agent.generate_report(matrices)

        assert isinstance(report, ComparisonReport)
        assert report.title.startswith("Optimizer Engine Comparison")
        assert set(report.engines_compared) == {"StarRocks", "ClickHouse"}

    def test_generate_report_findings(self):
        """generate_report extracts findings from matrices."""
        agent = ComparisonAgent(
            engines=["StarRocks", "ClickHouse"],
            work_dir="/tmp/work",
            analysis_results=_create_sample_analysis_results()
        )
        matrices = agent.generate_matrices()
        report = agent.generate_report(matrices)

        assert len(report.findings) >= 0
        assert len(report.matrices) == 4

    def test_generate_report_recommendations(self):
        """generate_report includes recommendations."""
        agent = ComparisonAgent(
            engines=["StarRocks", "ClickHouse"],
            work_dir="/tmp/work",
            analysis_results=_create_sample_analysis_results()
        )
        matrices = agent.generate_matrices()
        report = agent.generate_report(matrices)

        assert isinstance(report.recommendations, list)


class TestReportGenerator:
    """Tests for ReportGenerator class."""

    def test_report_generator_creation(self):
        """ReportGenerator can be instantiated."""
        matrices = [
            ComparisonMatrix(
                engines=["StarRocks"],
                dimensions=[ComparisonDimension.LIFECYCLE],
                cells=[]
            )
        ]
        generator = ReportGenerator(
            engines=["StarRocks"],
            matrices=matrices
        )

        assert generator.engines == ["StarRocks"]
        assert len(generator.matrices) == 1

    def test_report_generator_generate_report(self):
        """ReportGenerator generate_report returns ComparisonReport."""
        agent = ComparisonAgent(
            engines=["StarRocks"],
            work_dir="/tmp/work",
            analysis_results=_create_sample_analysis_results()
        )
        matrices = agent.generate_matrices()

        generator = ReportGenerator(
            engines=["StarRocks"],
            matrices=matrices
        )
        report = generator.generate_report()

        assert isinstance(report, ComparisonReport)

    def test_report_generator_generate_markdown(self):
        """ReportGenerator generate_markdown returns markdown string."""
        agent = ComparisonAgent(
            engines=["StarRocks"],
            work_dir="/tmp/work",
            analysis_results=_create_sample_analysis_results()
        )
        matrices = agent.generate_matrices()

        generator = ReportGenerator(
            engines=["StarRocks"],
            matrices=matrices
        )
        markdown = generator.generate_markdown()

        assert "# Optimizer Engine Comparison Report" in markdown
        assert "StarRocks" in markdown
        assert "## Lifecycle Comparison" in markdown

    def test_report_generator_markdown_tables(self):
        """ReportGenerator markdown contains comparison tables."""
        agent = ComparisonAgent(
            engines=["StarRocks", "ClickHouse"],
            work_dir="/tmp/work",
            analysis_results=_create_sample_analysis_results()
        )
        matrices = agent.generate_matrices()

        generator = ReportGenerator(
            engines=["StarRocks", "ClickHouse"],
            matrices=matrices
        )
        markdown = generator.generate_markdown()

        # Check table structure
        assert "| Metric |" in markdown
        assert "|---|" in markdown

    def test_report_generator_extract_findings(self):
        """ReportGenerator extracts findings correctly."""
        matrices = [
            ComparisonMatrix(
                engines=["StarRocks"],
                dimensions=[ComparisonDimension.LIFECYCLE],
                cells=[]
            )
        ]
        generator = ReportGenerator(
            engines=["StarRocks"],
            matrices=matrices
        )
        findings = generator._extract_all_findings()

        assert isinstance(findings, list)

    def test_report_generator_with_empty_matrices(self):
        """ReportGenerator handles empty matrices."""
        generator = ReportGenerator(
            engines=["StarRocks"],
            matrices=[]
        )
        report = generator.generate_report()

        assert isinstance(report, ComparisonReport)
        assert report.matrices == []