"""Tests for comparison matrix generation."""

import tempfile
from pathlib import Path

from optimizer_analysis.comparison.matrix import MatrixGenerator
from optimizer_analysis.schemas import (
    ComparisonDimension,
    ComparisonMatrix,
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


def _create_sample_framework():
    """Create a sample Framework for testing."""
    return Framework(
        engine_name="StarRocks",
        engine_type=EngineType.COLUMNAR_OLAP,
        optimizer_style=OptimizerStyle.CASCADES,
        main_entry="OptimizedExpr.deriveProperty()",
        optimizer_phases=[
            OptimizerPhase.PARSING,
            OptimizerPhase.LOGICAL_OPT,
            OptimizerPhase.PHYSICAL_OPT,
            OptimizerPhase.COST_ESTIMATION,
        ],
        logical_physical_split=True,
        memo_or_equivalent="Memo structure in Cascades style",
        search_strategy="Branch and bound with pruning",
        evidence=[
            Evidence(
                file_path="src/optimizer/optimizer.cpp",
                description="Main optimizer entry point",
                evidence_type=EvidenceType.SOURCE_CODE
            )
        ]
    )


def _create_sample_rules():
    """Create sample rules for testing."""
    return [
        Rule(
            rule_id="SR001",
            rule_name="PushDownJoin",
            engine="StarRocks",
            rule_category=RuleCategory.CBO,
            source_files=["src/optimizer/rules/join_pushdown.cpp"]
        ),
        Rule(
            rule_id="SR002",
            rule_name="MergeProject",
            engine="StarRocks",
            rule_category=RuleCategory.RBO,
            source_files=["src/optimizer/rules/project_merge.cpp"]
        ),
        Rule(
            rule_id="SR003",
            rule_name="SimplifyScalar",
            engine="StarRocks",
            rule_category=RuleCategory.SCALAR,
            source_files=["src/optimizer/rules/scalar_simplify.cpp"]
        ),
        Rule(
            rule_id="SR004",
            rule_name="PostOptRewrite",
            engine="StarRocks",
            rule_category=RuleCategory.POST_OPT,
            source_files=["src/optimizer/rules/post_opt.cpp"]
        ),
        Rule(
            rule_id="SR005",
            rule_name="PushDownFilter",
            engine="StarRocks",
            rule_category=RuleCategory.CBO,
            source_files=["src/optimizer/rules/filter_pushdown.cpp"]
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
                    file_path="src/optimizer/property/distribution.cpp",
                    description="Distribution property definition",
                    evidence_type=EvidenceType.SOURCE_CODE
                )
            ]
        ),
        TraitProperty(
            property_name="OrderingProperty",
            property_type=PropertyType.PHYSICAL,
            enforcer="SortEnforcer",
            evidence=[
                Evidence(
                    file_path="src/optimizer/property/ordering.cpp",
                    description="Ordering property definition",
                    evidence_type=EvidenceType.SOURCE_CODE
                )
            ]
        ),
    ]


def _create_sample_observability():
    """Create sample observability for testing."""
    return Observability(
        explain_interfaces=["EXPLAIN", "EXPLAIN ANALYZE", "EXPLAIN VERBOSE"],
        trace_interfaces=["optimizer_trace", "memo_dump"],
        rule_fire_visibility="partial",
        memo_dump_support=True,
        session_controls=["optimizer_switch", "cost_threshold"],
        evidence=[
            Evidence(
                file_path="src/optimizer/explain.cpp",
                description="EXPLAIN implementation",
                evidence_type=EvidenceType.SOURCE_CODE
            )
        ]
    )


def _create_sample_engines_data():
    """Create sample engines data for testing."""
    return {
        "StarRocks": {
            "framework": _create_sample_framework(),
            "rules": _create_sample_rules(),
            "properties": _create_sample_properties(),
            "observability": _create_sample_observability(),
        },
        "PostgreSQL": {
            "framework": Framework(
                engine_name="PostgreSQL",
                engine_type=EngineType.ROW_STORE,
                optimizer_style=OptimizerStyle.PLANNER_PATH_ENUM,
                main_entry="planner.c",
                optimizer_phases=[
                    OptimizerPhase.PARSING,
                    OptimizerPhase.LOGICAL_OPT,
                ],
                logical_physical_split=False,
                memo_or_equivalent=None,
                evidence=[
                    Evidence(
                        file_path="src/backend/optimizer/planner.c",
                        description="PostgreSQL planner entry",
                        evidence_type=EvidenceType.SOURCE_CODE
                    )
                ]
            ),
            "rules": [
                Rule(
                    rule_id="PG001",
                    rule_name="push_down_join",
                    engine="PostgreSQL",
                    rule_category=RuleCategory.RBO,
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


def test_matrix_generator_init():
    """Test MatrixGenerator initialization."""
    engines_data = _create_sample_engines_data()
    generator = MatrixGenerator(engines_data)

    assert generator.engines_data == engines_data
    assert set(generator.engine_names) == {"StarRocks", "PostgreSQL"}


def test_generate_lifecycle_matrix():
    """Test lifecycle matrix generation."""
    engines_data = _create_sample_engines_data()
    generator = MatrixGenerator(engines_data)
    matrix = generator.generate_lifecycle_matrix()

    assert isinstance(matrix, ComparisonMatrix)
    assert set(matrix.engines) == {"StarRocks", "PostgreSQL"}
    assert matrix.dimensions == [ComparisonDimension.LIFECYCLE]

    # Each engine has 4 metrics: style, split, memo, phases
    # 2 engines * 4 metrics = 8 cells
    assert len(matrix.cells) == 8

    # Check StarRocks cells
    starrocks_cells = [c for c in matrix.cells if c.engine == "StarRocks"]
    assert len(starrocks_cells) == 4

    # Verify optimizer_style
    style_cell = starrocks_cells[0]
    assert style_cell.value == "cascades"
    assert style_cell.dimension == ComparisonDimension.LIFECYCLE

    # Verify logical_physical_split
    split_cell = starrocks_cells[1]
    assert split_cell.value == "yes"

    # Verify memo_support
    memo_cell = starrocks_cells[2]
    assert memo_cell.value == "yes"

    # Verify phases_present
    phases_cell = starrocks_cells[3]
    assert "parsing" in phases_cell.value.lower()


def test_generate_rule_coverage_matrix():
    """Test rule coverage matrix generation."""
    engines_data = _create_sample_engines_data()
    generator = MatrixGenerator(engines_data)
    matrix = generator.generate_rule_coverage_matrix()

    assert isinstance(matrix, ComparisonMatrix)
    assert matrix.dimensions == [ComparisonDimension.RULE_COVERAGE]

    # Each engine has 4 metrics: rbo, cbo, scalar, post_opt
    # 2 engines * 4 metrics = 8 cells
    assert len(matrix.cells) == 8

    # Check StarRocks cells
    starrocks_cells = [c for c in matrix.cells if c.engine == "StarRocks"]
    assert len(starrocks_cells) == 4

    # Verify counts (StarRocks has: 1 RBO, 2 CBO, 1 SCALAR, 1 POST_OPT)
    assert starrocks_cells[0].value == "1"  # RBO count
    assert starrocks_cells[1].value == "2"  # CBO count
    assert starrocks_cells[2].value == "1"  # SCALAR count
    assert starrocks_cells[3].value == "1"  # POST_OPT count


def test_generate_property_matrix():
    """Test property matrix generation."""
    engines_data = _create_sample_engines_data()
    generator = MatrixGenerator(engines_data)
    matrix = generator.generate_property_matrix()

    assert isinstance(matrix, ComparisonMatrix)
    assert matrix.dimensions == [ComparisonDimension.PROPERTY_SYSTEM]

    # Each engine has 3 metrics: distribution, ordering, enforcers
    # 2 engines * 3 metrics = 6 cells
    assert len(matrix.cells) == 6

    # Check StarRocks cells (has distribution and ordering properties with enforcers)
    starrocks_cells = [c for c in matrix.cells if c.engine == "StarRocks"]
    assert len(starrocks_cells) == 3

    # Distribution support: StarRocks has 1 distribution property
    assert starrocks_cells[0].value == "1"

    # Ordering support: StarRocks has 1 ordering property
    assert starrocks_cells[1].value == "1"

    # Enforcer mechanisms: StarRocks has 2 enforcers
    assert starrocks_cells[2].value == "2"


def test_generate_observability_matrix():
    """Test observability matrix generation."""
    engines_data = _create_sample_engines_data()
    generator = MatrixGenerator(engines_data)
    matrix = generator.generate_observability_matrix()

    assert isinstance(matrix, ComparisonMatrix)
    assert matrix.dimensions == [ComparisonDimension.OBSERVABILITY]

    # Each engine has 4 metrics: explain, trace, memo_dump, session
    # 2 engines * 4 metrics = 8 cells
    assert len(matrix.cells) == 8

    # Check StarRocks cells
    starrocks_cells = [c for c in matrix.cells if c.engine == "StarRocks"]
    assert len(starrocks_cells) == 4

    # Explain support: StarRocks has 3 explain interfaces
    assert starrocks_cells[0].value == "3"

    # Trace support: StarRocks has 2 trace interfaces
    assert starrocks_cells[1].value == "2"

    # Memo dump support: StarRocks supports it
    assert starrocks_cells[2].value == "yes"

    # Session controls: StarRocks has 2 session controls
    assert starrocks_cells[3].value == "2"


def test_generate_all_matrices():
    """Test generation of all matrices."""
    engines_data = _create_sample_engines_data()
    generator = MatrixGenerator(engines_data)
    matrices = generator.generate_all_matrices()

    assert len(matrices) == 4

    # Check each matrix type
    dimensions = [m.dimensions[0] for m in matrices]
    assert ComparisonDimension.LIFECYCLE in dimensions
    assert ComparisonDimension.RULE_COVERAGE in dimensions
    assert ComparisonDimension.PROPERTY_SYSTEM in dimensions
    assert ComparisonDimension.OBSERVABILITY in dimensions


def test_to_dataframe():
    """Test conversion to dataframe format."""
    engines_data = _create_sample_engines_data()
    generator = MatrixGenerator(engines_data)
    matrix = generator.generate_lifecycle_matrix()

    df = generator.to_dataframe(matrix)

    assert "columns" in df
    assert "data" in df
    assert "dimension" in df
    assert "generated_at" in df

    assert df["columns"] == ["metric", "StarRocks", "PostgreSQL"]
    assert df["dimension"] == "lifecycle"

    # Check data rows
    assert len(df["data"]) == 4  # 4 metrics for lifecycle

    # Check first row (optimizer_style)
    first_row = df["data"][0]
    assert first_row["metric"] == "optimizer_style"
    assert "StarRocks" in first_row
    assert "PostgreSQL" in first_row


def test_to_csv():
    """Test CSV output."""
    engines_data = _create_sample_engines_data()
    generator = MatrixGenerator(engines_data)
    matrix = generator.generate_lifecycle_matrix()

    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "lifecycle_comparison.csv"
        generator.to_csv(matrix, str(csv_path))

        assert csv_path.exists()

        # Read and verify CSV content
        content = csv_path.read_text()
        lines = content.strip().split("\n")

        # Check header
        assert "metric" in lines[0]
        assert "StarRocks" in lines[0]
        assert "PostgreSQL" in lines[0]

        # Check we have data rows (header + 4 metrics = 5 lines)
        assert len(lines) == 5


def test_to_csv_creates_directory():
    """Test that to_csv creates parent directories if needed."""
    engines_data = _create_sample_engines_data()
    generator = MatrixGenerator(engines_data)
    matrix = generator.generate_lifecycle_matrix()

    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "subdir" / "nested" / "output.csv"
        generator.to_csv(matrix, str(csv_path))

        assert csv_path.exists()


def test_empty_engines_data():
    """Test with empty engines data."""
    generator = MatrixGenerator({})

    # Should not raise errors
    matrix = generator.generate_lifecycle_matrix()
    assert matrix.engines == []
    assert matrix.cells == []

    matrices = generator.generate_all_matrices()
    assert len(matrices) == 4


def test_missing_engine_data():
    """Test with partially missing engine data."""
    engines_data = {
        "Engine1": {
            # No framework, rules, properties, or observability
        }
    }
    generator = MatrixGenerator(engines_data)

    # Should not raise errors with missing data
    matrix = generator.generate_lifecycle_matrix()
    assert matrix.engines == ["Engine1"]
    # All cells should have "n/a" or default values
    for cell in matrix.cells:
        assert cell.value in ["n/a", "no", "none"]


def test_multiple_engines():
    """Test with multiple engines."""
    engines_data = _create_sample_engines_data()

    # Add a third engine
    engines_data["MySQL"] = {
        "framework": Framework(
            engine_name="MySQL",
            engine_type=EngineType.ROW_STORE,
            optimizer_style=OptimizerStyle.HEURISTIC_MIXED,
            main_entry="sql_optimizer.cc",
            optimizer_phases=[OptimizerPhase.PARSING],
            logical_physical_split=False,
            memo_or_equivalent=None,
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

    generator = MatrixGenerator(engines_data)

    matrix = generator.generate_lifecycle_matrix()
    assert len(matrix.engines) == 3

    # Each engine has 4 cells for lifecycle
    assert len(matrix.cells) == 12

    # Verify each engine has cells
    for engine in ["StarRocks", "PostgreSQL", "MySQL"]:
        engine_cells = [c for c in matrix.cells if c.engine == engine]
        assert len(engine_cells) == 4