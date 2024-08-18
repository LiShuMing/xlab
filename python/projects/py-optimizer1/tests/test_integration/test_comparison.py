"""Integration tests for Comparison functionality.

This module tests the full comparison workflow including ComparisonAgent,
VerifierAgent, MatrixGenerator, and ReportGenerator working together.
"""

import json
import tempfile
from os.path import exists, join
from pathlib import Path

from optimizer_analysis.agents.base import AgentResult
from optimizer_analysis.agents.comparison_agent import ComparisonAgent, ReportGenerator
from optimizer_analysis.agents.verifier_agent import VerifierAgent, VerificationResult
from optimizer_analysis.agents.lifecycle import LifecycleInfo, PhaseInfo
from optimizer_analysis.comparison.matrix import MatrixGenerator
from optimizer_analysis.comparison.report import ReportGenerator as MatrixReportGenerator
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


# Sample StarRocks-like engine data
STARROCKS_DATA = {
    "framework": Framework(
        engine_name="StarRocks",
        engine_type=EngineType.COLUMNAR_OLAP,
        optimizer_style=OptimizerStyle.CASCADES,
        main_entry="com.starrocks.sql.optimizer.Optimizer",
        optimizer_phases=[
            OptimizerPhase.PARSING,
            OptimizerPhase.LOGICAL_OPT,
            OptimizerPhase.PHYSICAL_OPT,
            OptimizerPhase.COST_ESTIMATION,
            OptimizerPhase.BEST_PLAN_SELECTION,
        ],
        logical_physical_split=True,
        memo_or_equivalent="Memo.java",
        search_strategy="Cascades-style search with memoization",
        best_plan_selection="Cost-based selection from memo groups",
        evidence=[
            Evidence(
                file_path="sql/optimizer/Optimizer.java",
                description="Main optimizer entry point",
                evidence_type=EvidenceType.SOURCE_CODE,
                line_start=1,
                line_end=100
            )
        ]
    ),
    "rules": [
        Rule(
            rule_id="SR-RBO-001",
            rule_name="PushFilterDown",
            engine="StarRocks",
            rule_category=RuleCategory.RBO,
            source_files=["sql/optimizer/rule/transformation/PushDownFilterRule.java"],
            lifecycle_stage="logical_opt",
            trigger_pattern="Filter -> Scan",
            evidence=[
                Evidence(
                    file_path="sql/optimizer/rule/transformation/PushDownFilterRule.java",
                    description="Filter pushdown transformation rule",
                    evidence_type=EvidenceType.SOURCE_CODE
                )
            ]
        ),
        Rule(
            rule_id="SR-CBO-001",
            rule_name="JoinReorderDP",
            engine="StarRocks",
            rule_category=RuleCategory.CBO,
            source_files=["sql/optimizer/rule/transformation/ReorderJoinRule.java"],
            depends_on_cost=True,
            depends_on_stats=True,
            evidence=[
                Evidence(
                    file_path="sql/optimizer/rule/transformation/ReorderJoinRule.java",
                    description="Join reorder using DP algorithm",
                    evidence_type=EvidenceType.SOURCE_CODE
                )
            ]
        ),
        Rule(
            rule_id="SR-SCALAR-001",
            rule_name="SimplifyCast",
            engine="StarRocks",
            rule_category=RuleCategory.SCALAR,
            source_files=["sql/optimizer/rule/transformation/SimplifyCastRule.java"],
            evidence=[
                Evidence(
                    file_path="sql/optimizer/rule/transformation/SimplifyCastRule.java",
                    description="Scalar cast simplification",
                    evidence_type=EvidenceType.SOURCE_CODE
                )
            ]
        ),
    ],
    "properties": [
        TraitProperty(
            property_name="DistributionProperty",
            property_type=PropertyType.PHYSICAL,
            enforcer="DistributionEnforcer",
            where_used=["HashJoin", "Aggregation"],
            evidence=[
                Evidence(
                    file_path="sql/optimizer/property/DistributionProperty.java",
                    description="Distribution property for parallel execution",
                    evidence_type=EvidenceType.SOURCE_CODE
                )
            ]
        ),
        TraitProperty(
            property_name="OrderingProperty",
            property_type=PropertyType.PHYSICAL,
            enforcer="SortEnforcer",
            where_used=["OrderBy", "MergeJoin"],
            evidence=[
                Evidence(
                    file_path="sql/optimizer/property/OrderingProperty.java",
                    description="Ordering property for sort requirements",
                    evidence_type=EvidenceType.SOURCE_CODE
                )
            ]
        ),
    ],
    "observability": Observability(
        explain_interfaces=["EXPLAIN", "EXPLAIN ANALYZE", "EXPLAIN VERBOSE"],
        trace_interfaces=["optimizer_trace", "query_dump"],
        rule_fire_visibility="partial",
        memo_dump_support=True,
        session_controls=["optimizer_switch", "optimizer_enable_rule"],
        evidence=[
            Evidence(
                file_path="sql/optimizer/dump/QueryDump.java",
                description="Query dump for optimizer inspection",
                evidence_type=EvidenceType.SOURCE_CODE
            )
        ]
    ),
    "lifecycle": LifecycleInfo(
        engine="StarRocks",
        phases=[
            PhaseInfo(
                phase="Parsing",
                entry="SqlParser",
                description="SQL parsing and AST generation",
                transitions_to=["Analysis"]
            ),
            PhaseInfo(
                phase="Analysis",
                entry="Analyzer",
                description="Semantic analysis and query rewriting",
                transitions_to=["LogicalPlanning"]
            ),
            PhaseInfo(
                phase="LogicalPlanning",
                entry="Optimizer",
                description="Logical plan generation and transformation",
                transitions_to=["PhysicalPlanning"]
            ),
            PhaseInfo(
                phase="PhysicalPlanning",
                entry="Optimizer",
                description="Physical plan generation with cost estimation",
                transitions_to=["Execution"]
            ),
            PhaseInfo(
                phase="Execution",
                entry="ExecutionPlanBuilder",
                description="Plan execution",
                transitions_to=[]
            ),
        ],
        phase_sequence=["Parsing", "Analysis", "LogicalPlanning", "PhysicalPlanning", "Execution"],
        logical_physical_boundary="LogicalPlanning -> PhysicalPlanning",
        best_plan_selection="Cost-based from Memo",
        confidence="high",
        notes=["Cascades-style optimizer with memoization"]
    ),
}


# Sample PostgreSQL-like engine data
POSTGRESQL_DATA = {
    "framework": Framework(
        engine_name="PostgreSQL",
        engine_type=EngineType.ROW_STORE,
        optimizer_style=OptimizerStyle.VOLCANO,
        main_entry="planner.c",
        optimizer_phases=[
            OptimizerPhase.PARSING,
            OptimizerPhase.LOGICAL_OPT,
            OptimizerPhase.PHYSICAL_OPT,
        ],
        logical_physical_split=False,
        memo_or_equivalent=None,
        search_strategy="Dynamic programming with geqo for large joins",
        best_plan_selection="Cheapest path selection",
        evidence=[
            Evidence(
                file_path="src/backend/optimizer/plan/planner.c",
                description="Main planner entry point",
                evidence_type=EvidenceType.SOURCE_CODE
            )
        ]
    ),
    "rules": [
        Rule(
            rule_id="PG-RBO-001",
            rule_name="ReduceOuterJoin",
            engine="PostgreSQL",
            rule_category=RuleCategory.RBO,
            source_files=["src/backend/optimizer/plan/subselect.c"],
            lifecycle_stage="logical_opt",
            evidence=[
                Evidence(
                    file_path="src/backend/optimizer/util/pathnode.c",
                    description="Path creation for join reduction",
                    evidence_type=EvidenceType.SOURCE_CODE
                )
            ]
        ),
        Rule(
            rule_id="PG-CBO-001",
            rule_name="ChooseIndexScan",
            engine="PostgreSQL",
            rule_category=RuleCategory.CBO,
            source_files=["src/backend/optimizer/path/indxpath.c"],
            depends_on_cost=True,
            depends_on_stats=True,
            evidence=[
                Evidence(
                    file_path="src/backend/optimizer/cost/costsize.c",
                    description="Cost estimation for index scan",
                    evidence_type=EvidenceType.SOURCE_CODE
                )
            ]
        ),
    ],
    "properties": [
        TraitProperty(
            property_name="PathKeys",
            property_type=PropertyType.PHYSICAL,
            enforcer="Sort",
            where_used=["MergeJoin", "OrderBy"],
            evidence=[
                Evidence(
                    file_path="src/backend/optimizer/util/pathkeys.c",
                    description="Path keys for ordering",
                    evidence_type=EvidenceType.SOURCE_CODE
                )
            ]
        ),
    ],
    "observability": Observability(
        explain_interfaces=["EXPLAIN", "EXPLAIN ANALYZE"],
        trace_interfaces=[],
        rule_fire_visibility="none",
        memo_dump_support=False,
        session_controls=["enable_seqscan", "enable_indexscan", "geqo_threshold"],
        evidence=[
            Evidence(
                file_path="src/backend/commands/explain.c",
                description="EXPLAIN command implementation",
                evidence_type=EvidenceType.SOURCE_CODE
            )
        ]
    ),
    "lifecycle": LifecycleInfo(
        engine="PostgreSQL",
        phases=[
            PhaseInfo(
                phase="Parsing",
                entry="postgres.c",
                description="SQL parsing",
                transitions_to=["Rewrite"]
            ),
            PhaseInfo(
                phase="Rewrite",
                entry="rewrite.c",
                description="Query rewriting",
                transitions_to=["Planner"]
            ),
            PhaseInfo(
                phase="Planner",
                entry="planner.c",
                description="Plan generation",
                transitions_to=["Executor"]
            ),
            PhaseInfo(
                phase="Executor",
                entry="execMain.c",
                description="Plan execution",
                transitions_to=[]
            ),
        ],
        phase_sequence=["Parsing", "Rewrite", "Planner", "Executor"],
        logical_physical_boundary="None",
        best_plan_selection="Cheapest path",
        confidence="medium",
        notes=["Volcano-style optimizer without explicit memoization"]
    ),
}


class TestComparisonIntegration:
    """Integration tests for comparison workflow."""

    def test_compare_two_engines(self):
        """Compare StarRocks vs PostgreSQL mock data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = join(tmpdir, "comparison_work")

            analysis_results = {
                "StarRocks": STARROCKS_DATA,
                "PostgreSQL": POSTGRESQL_DATA,
            }

            agent = ComparisonAgent(
                engines=["StarRocks", "PostgreSQL"],
                work_dir=work_dir,
                analysis_results=analysis_results
            )

            result = agent.execute()

            # Verify AgentResult
            assert isinstance(result, AgentResult)
            assert result.agent_name == "ComparisonAgent"
            assert result.status in ["success", "partial"]

            # Verify artifacts created
            assert len(result.artifacts) == 2

            # Verify comparison directory created
            comparison_dir = join(work_dir, "comparison")
            assert exists(comparison_dir)

            # Verify matrix.json created
            matrix_json_path = join(comparison_dir, "matrix.json")
            assert exists(matrix_json_path)

            # Load and verify matrix.json content
            with open(matrix_json_path) as f:
                matrix_data = json.load(f)

            assert "engines" in matrix_data
            assert set(matrix_data["engines"]) == {"StarRocks", "PostgreSQL"}
            assert "matrices" in matrix_data
            assert len(matrix_data["matrices"]) >= 4

            # Verify report.md created
            report_md_path = join(comparison_dir, "report.md")
            assert exists(report_md_path)

            # Load and verify report.md content
            with open(report_md_path) as f:
                report_content = f.read()

            assert "# Optimizer Engine Comparison Report" in report_content
            assert "StarRocks" in report_content
            assert "PostgreSQL" in report_content

            # Verify metadata
            assert result.metadata["engines_compared"] == ["StarRocks", "PostgreSQL"]
            assert result.metadata["matrices_count"] >= 4

    def test_matrix_generation(self):
        """Test MatrixGenerator with real data structure."""
        analysis_results = {
            "StarRocks": STARROCKS_DATA,
            "PostgreSQL": POSTGRESQL_DATA,
        }

        generator = MatrixGenerator(analysis_results)

        # Generate all matrices
        matrices = generator.generate_all_matrices()

        assert len(matrices) == 4

        # Test lifecycle matrix
        lifecycle_matrix = generator.generate_lifecycle_matrix()
        assert isinstance(lifecycle_matrix, ComparisonMatrix)
        assert lifecycle_matrix.dimensions == [ComparisonDimension.LIFECYCLE]
        assert set(lifecycle_matrix.engines) == {"StarRocks", "PostgreSQL"}

        # Verify lifecycle matrix has cells for both engines
        starrocks_cells = [c for c in lifecycle_matrix.cells if c.engine == "StarRocks"]
        postgres_cells = [c for c in lifecycle_matrix.cells if c.engine == "PostgreSQL"]

        assert len(starrocks_cells) >= 4
        assert len(postgres_cells) >= 4

        # Check optimizer style values
        assert starrocks_cells[0].value == "cascades"
        assert postgres_cells[0].value == "volcano"

        # Test rule coverage matrix
        rule_matrix = generator.generate_rule_coverage_matrix()
        assert isinstance(rule_matrix, ComparisonMatrix)
        assert rule_matrix.dimensions == [ComparisonDimension.RULE_COVERAGE]

        # Verify rule counts are present
        sr_rule_cells = [c for c in rule_matrix.cells if c.engine == "StarRocks"]
        pg_rule_cells = [c for c in rule_matrix.cells if c.engine == "PostgreSQL"]

        assert len(sr_rule_cells) >= 4
        assert len(pg_rule_cells) >= 4

        # Test property matrix
        property_matrix = generator.generate_property_matrix()
        assert isinstance(property_matrix, ComparisonMatrix)
        assert property_matrix.dimensions == [ComparisonDimension.PROPERTY_SYSTEM]

        # Test observability matrix
        observability_matrix = generator.generate_observability_matrix()
        assert isinstance(observability_matrix, ComparisonMatrix)
        assert observability_matrix.dimensions == [ComparisonDimension.OBSERVABILITY]

        # Verify observability values
        sr_obs_cells = [c for c in observability_matrix.cells if c.engine == "StarRocks"]
        pg_obs_cells = [c for c in observability_matrix.cells if c.engine == "PostgreSQL"]

        # StarRocks has 3 explain interfaces
        assert sr_obs_cells[0].value == "3"
        # PostgreSQL has 2 explain interfaces
        assert pg_obs_cells[0].value == "2"

        # StarRocks has memo dump support
        assert sr_obs_cells[2].value == "yes"
        # PostgreSQL does not
        assert pg_obs_cells[2].value == "no"

    def test_report_generation(self):
        """Test ReportGenerator with matrices."""
        analysis_results = {
            "StarRocks": STARROCKS_DATA,
            "PostgreSQL": POSTGRESQL_DATA,
        }

        generator = MatrixGenerator(analysis_results)
        matrices = generator.generate_all_matrices()

        # Test matrix-based ReportGenerator
        report_generator = MatrixReportGenerator(matrices)

        # Generate markdown report
        markdown_report = report_generator.generate_markdown_report()
        assert "# Optimizer Engine Comparison Report" in markdown_report
        assert "## Comparison Tables" in markdown_report
        assert "## Key Findings" in markdown_report
        assert "## Recommendations" in markdown_report

        # Generate JSON report
        json_report = report_generator.generate_json_report()
        report_data = json.loads(json_report)

        assert report_data["title"] == "Optimizer Engine Comparison Report"
        assert set(report_data["engines_compared"]) == {"StarRocks", "PostgreSQL"}
        assert len(report_data["matrices"]) >= 4
        assert isinstance(report_data["findings"], list)
        assert isinstance(report_data["recommendations"], list)

        # Verify findings extraction
        findings = report_generator.identify_findings()
        assert isinstance(findings, list)
        assert len(findings) > 0  # Should have findings from comparison

        # Verify recommendations generation
        recommendations = report_generator.generate_recommendations()
        assert isinstance(recommendations, list)

        # Test save report
        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = join(tmpdir, "report.md")
            json_path = join(tmpdir, "report.json")

            report_generator.save_report(md_path, format="markdown")
            report_generator.save_report(json_path, format="json")

            assert exists(md_path)
            assert exists(json_path)

    def test_verification_flow(self):
        """Test VerifierAgent with analysis results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = join(tmpdir, "verification_work")

            # Create analysis result with some issues for verification
            analysis_result = {
                "rules": STARROCKS_DATA["rules"],
                "framework": STARROCKS_DATA["framework"],
                "lifecycle": STARROCKS_DATA["lifecycle"],
            }

            verifier = VerifierAgent(
                engine="StarRocks",
                work_dir=work_dir,
                analysis_result=analysis_result
            )

            result = verifier.execute()

            # Verify AgentResult
            assert isinstance(result, AgentResult)
            assert result.agent_name == "VerifierAgent"
            assert result.status in ["success", "partial", "failed"]

            # Verify artifacts created
            assert len(result.artifacts) > 0

            # Verify verification directory created
            verification_dir = join(work_dir, "verification")
            assert exists(verification_dir)

            # Verify verification_result.json created
            verification_json_path = join(verification_dir, "verification_result.json")
            assert exists(verification_json_path)

            # Load and verify verification result
            with open(verification_json_path) as f:
                verification_data = json.load(f)

            assert verification_data["engine"] == "StarRocks"
            assert "passed" in verification_data
            assert "issues" in verification_data
            assert "checked_items" in verification_data

            # Test verify_all method
            all_result = verifier.verify_all()
            assert isinstance(all_result, VerificationResult)
            assert all_result.engine == "StarRocks"

            # Test with data that should have issues
            problematic_analysis = {
                "rules": [
                    Rule(
                        rule_id="UNKNOWN",
                        rule_name="TestRule",
                        engine="TestEngine",
                        rule_category=RuleCategory.RBO,
                        source_files=[],  # Empty source files - should cause error
                        confidence="unknown",  # Unknown confidence without uncertain_points
                    )
                ],
                "framework": Framework(
                    engine_name="TestEngine",
                    engine_type=EngineType.COLUMNAR_OLAP,
                    optimizer_style=OptimizerStyle.CASCADES,
                    main_entry="test.cpp",
                    evidence=[]  # No evidence - should cause error
                ),
                "lifecycle": LifecycleInfo(
                    engine="TestEngine",
                    phases=[],  # Empty phases - should cause error
                    phase_sequence=["Phase1", "Phase2"],  # Phase in sequence but not in phases
                    confidence="unknown",  # Unknown confidence without notes
                )
            }

            verifier_with_issues = VerifierAgent(
                engine="TestEngine",
                work_dir=work_dir,
                analysis_result=problematic_analysis
            )

            issues_result = verifier_with_issues.verify_all()

            # Should have errors
            assert issues_result.errors > 0
            assert not issues_result.passed

            # Check for specific issue categories
            error_categories = [i.category for i in issues_result.issues if i.severity == "error"]
            assert "rule" in error_categories  # Empty source_files
            assert "evidence" in error_categories  # No evidence

    def test_full_comparison_pipeline(self):
        """End-to-end test: analyze -> verify -> compare -> report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_work_dir = join(tmpdir, "full_pipeline")

            # Phase 1: Prepare analysis results (simulating analyze phase)
            starrocks_work_dir = join(base_work_dir, "StarRocks")
            postgres_work_dir = join(base_work_dir, "PostgreSQL")

            # Phase 2: Verify each engine's analysis
            # Verify StarRocks
            starrocks_verifier = VerifierAgent(
                engine="StarRocks",
                work_dir=starrocks_work_dir,
                analysis_result={
                    "rules": STARROCKS_DATA["rules"],
                    "framework": STARROCKS_DATA["framework"],
                    "lifecycle": STARROCKS_DATA["lifecycle"],
                }
            )
            starrocks_verify_result = starrocks_verifier.execute()

            assert isinstance(starrocks_verify_result, AgentResult)
            assert starrocks_verify_result.status in ["success", "partial"]

            # Verify PostgreSQL
            postgres_verifier = VerifierAgent(
                engine="PostgreSQL",
                work_dir=postgres_work_dir,
                analysis_result={
                    "rules": POSTGRESQL_DATA["rules"],
                    "framework": POSTGRESQL_DATA["framework"],
                    "lifecycle": POSTGRESQL_DATA["lifecycle"],
                }
            )
            postgres_verify_result = postgres_verifier.execute()

            assert isinstance(postgres_verify_result, AgentResult)
            assert postgres_verify_result.status in ["success", "partial"]

            # Phase 3: Compare engines
            comparison_work_dir = join(base_work_dir, "comparison")
            comparison_agent = ComparisonAgent(
                engines=["StarRocks", "PostgreSQL"],
                work_dir=comparison_work_dir,
                analysis_results={
                    "StarRocks": STARROCKS_DATA,
                    "PostgreSQL": POSTGRESQL_DATA,
                }
            )
            comparison_result = comparison_agent.execute()

            assert isinstance(comparison_result, AgentResult)
            assert comparison_result.status in ["success", "partial"]

            # Phase 4: Generate final report
            matrices = comparison_agent.generate_matrices()
            report_generator = MatrixReportGenerator(matrices)

            final_report_path = join(base_work_dir, "final_report.md")
            report_generator.save_report(final_report_path, format="markdown")

            assert exists(final_report_path)

            # Verify all artifacts are saved
            # StarRocks verification artifact
            starrocks_verify_json = join(starrocks_work_dir, "verification", "verification_result.json")
            assert exists(starrocks_verify_json)

            # PostgreSQL verification artifact
            postgres_verify_json = join(postgres_work_dir, "verification", "verification_result.json")
            assert exists(postgres_verify_json)

            # Comparison matrix artifact
            comparison_matrix_json = join(comparison_work_dir, "comparison", "matrix.json")
            assert exists(comparison_matrix_json)

            # Comparison report artifact
            comparison_report_md = join(comparison_work_dir, "comparison", "report.md")
            assert exists(comparison_report_md)

            # Final report
            assert exists(final_report_path)

            # Verify report content
            with open(final_report_path) as f:
                report_content = f.read()

            assert "# Optimizer Engine Comparison Report" in report_content
            assert "StarRocks" in report_content
            assert "PostgreSQL" in report_content
            assert "## Key Findings" in report_content
            assert "## Recommendations" in report_content

            # Load and verify matrix content
            with open(comparison_matrix_json) as f:
                matrix_data = json.load(f)

            assert "engines" in matrix_data
            assert len(matrix_data["matrices"]) >= 4

            # Verify that ComparisonAgent can compare multiple engines
            assert comparison_result.metadata["engines_compared"] == ["StarRocks", "PostgreSQL"]
            assert comparison_result.metadata["matrices_count"] >= 4

            # Verify VerifierAgent catches issues in problematic data
            problematic_engine_work_dir = join(base_work_dir, "ProblematicEngine")
            problematic_verifier = VerifierAgent(
                engine="ProblematicEngine",
                work_dir=problematic_engine_work_dir,
                analysis_result={
                    "rules": [
                        Rule(
                            rule_id="UNKNOWN",
                            rule_name="BadRule",
                            engine="ProblematicEngine",
                            rule_category=RuleCategory.RBO,
                            source_files=[],  # Empty - will cause error
                            confidence="unknown",  # Will cause error
                        )
                    ],
                    "framework": Framework(
                        engine_name="ProblematicEngine",
                        engine_type=EngineType.COLUMNAR_OLAP,
                        optimizer_style=OptimizerStyle.CASCADES,
                        main_entry="test.cpp",
                        evidence=[]  # Empty - will cause error
                    ),
                    "lifecycle": LifecycleInfo(
                        engine="ProblematicEngine",
                        phases=[],  # Empty - will cause error
                        phase_sequence=["A", "B"],
                        confidence="unknown",  # Will cause warning
                    )
                }
            )
            problematic_result = problematic_verifier.execute()

            # Verify VerifierAgent catches issues
            assert problematic_result.status in ["failed", "partial"]
            assert problematic_result.metadata["errors"] > 0 or problematic_result.metadata.get("passed") == False


class TestComparisonAgentMultipleEngines:
    """Additional tests for ComparisonAgent with multiple engines."""

    def test_comparison_agent_three_engines(self):
        """ComparisonAgent can compare three engines."""
        # Create a third engine mock
        MySQL_DATA = {
            "framework": Framework(
                engine_name="MySQL",
                engine_type=EngineType.ROW_STORE,
                optimizer_style=OptimizerStyle.HEURISTIC_MIXED,
                main_entry="sql_optimizer.cc",
                optimizer_phases=[OptimizerPhase.PARSING, OptimizerPhase.LOGICAL_OPT],
                logical_physical_split=False,
                memo_or_equivalent=None,
                evidence=[
                    Evidence(
                        file_path="sql/sql_optimizer.cc",
                        description="MySQL optimizer entry",
                        evidence_type=EvidenceType.SOURCE_CODE
                    )
                ]
            ),
            "rules": [
                Rule(
                    rule_id="MYSQL-RBO-001",
                    rule_name="ConstantPropagation",
                    engine="MySQL",
                    rule_category=RuleCategory.RBO,
                    source_files=["sql/sql_optimizer.cc"],
                ),
            ],
            "properties": [],
            "observability": Observability(
                explain_interfaces=["EXPLAIN", "EXPLAIN ANALYZE"],
                trace_interfaces=[],
                memo_dump_support=False,
                session_controls=["optimizer_switch"],
            ),
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = ComparisonAgent(
                engines=["StarRocks", "PostgreSQL", "MySQL"],
                work_dir=join(tmpdir, "work"),
                analysis_results={
                    "StarRocks": STARROCKS_DATA,
                    "PostgreSQL": POSTGRESQL_DATA,
                    "MySQL": MySQL_DATA,
                }
            )

            result = agent.execute()

            assert result.status in ["success", "partial"]
            assert result.metadata["engines_compared"] == ["StarRocks", "PostgreSQL", "MySQL"]

            # Verify matrices have cells for all three engines
            matrices = agent.generate_matrices()
            for matrix in matrices:
                assert set(matrix.engines) == {"StarRocks", "PostgreSQL", "MySQL"}

    def test_comparison_agent_empty_rules(self):
        """ComparisonAgent handles engines with no rules."""
        empty_rules_data = {
            "framework": Framework(
                engine_name="EmptyEngine",
                engine_type=EngineType.COLUMNAR_OLAP,
                optimizer_style=OptimizerStyle.CASCADES,
                main_entry="optimizer.cpp",
                evidence=[
                    Evidence(
                        file_path="optimizer.cpp",
                        description="Main optimizer",
                        evidence_type=EvidenceType.SOURCE_CODE
                    )
                ]
            ),
            "rules": [],
            "properties": [],
            "observability": Observability(
                explain_interfaces=["EXPLAIN"],
                trace_interfaces=[],
                memo_dump_support=False,
                session_controls=[],
            ),
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = ComparisonAgent(
                engines=["StarRocks", "EmptyEngine"],
                work_dir=join(tmpdir, "work"),
                analysis_results={
                    "StarRocks": STARROCKS_DATA,
                    "EmptyEngine": empty_rules_data,
                }
            )

            result = agent.execute()

            assert result.status in ["success", "partial"]

            # Verify rule matrix handles empty rules
            rule_matrix = agent.compare_rules()
            empty_cells = [c for c in rule_matrix.cells if c.engine == "EmptyEngine"]

            # All rule counts should be 0
            for cell in empty_cells:
                assert cell.value == "0"


class TestMatrixGeneratorDataframe:
    """Tests for MatrixGenerator to_dataframe functionality."""

    def test_to_dataframe_lifecycle(self):
        """Test to_dataframe for lifecycle matrix."""
        generator = MatrixGenerator({
            "StarRocks": STARROCKS_DATA,
            "PostgreSQL": POSTGRESQL_DATA,
        })

        lifecycle_matrix = generator.generate_lifecycle_matrix()
        df_data = generator.to_dataframe(lifecycle_matrix)

        assert "columns" in df_data
        assert "data" in df_data
        assert "dimension" in df_data

        assert df_data["dimension"] == "lifecycle"
        assert set(df_data["columns"]) == {"metric", "StarRocks", "PostgreSQL"}

        # Verify data rows
        assert len(df_data["data"]) == 4  # 4 metrics for lifecycle

    def test_to_dataframe_rule_coverage(self):
        """Test to_dataframe for rule coverage matrix."""
        generator = MatrixGenerator({
            "StarRocks": STARROCKS_DATA,
            "PostgreSQL": POSTGRESQL_DATA,
        })

        rule_matrix = generator.generate_rule_coverage_matrix()
        df_data = generator.to_dataframe(rule_matrix)

        assert df_data["dimension"] == "rule_coverage"
        assert len(df_data["data"]) == 4  # 4 metrics for rule coverage

    def test_to_csv(self):
        """Test to_csv for matrix export."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = MatrixGenerator({
                "StarRocks": STARROCKS_DATA,
                "PostgreSQL": POSTGRESQL_DATA,
            })

            lifecycle_matrix = generator.generate_lifecycle_matrix()
            csv_path = join(tmpdir, "lifecycle.csv")

            generator.to_csv(lifecycle_matrix, csv_path)

            assert exists(csv_path)

            # Verify CSV content
            with open(csv_path) as f:
                content = f.read()

            assert "metric" in content
            assert "StarRocks" in content
            assert "PostgreSQL" in content