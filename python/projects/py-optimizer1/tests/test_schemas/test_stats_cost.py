# tests/test_schemas/test_stats_cost.py
"""Tests for Statistics and Cost schemas."""
from optimizer_analysis.schemas.stats_cost import StatisticsInfo, CostModel, StatsGranularity
from optimizer_analysis.schemas.base import Evidence


def test_statistics_info_creation():
    """StatisticsInfo must have source and granularity."""
    stats = StatisticsInfo(
        stats_source="TableStatistics",
        stats_objects=["ndv", "row_count", "null_count", "min_max"],
        stats_granularity=StatsGranularity.COLUMN,
        storage_location="Statistics cache in memory",
        collection_trigger="Analyze table command",
        collection_scheduler="Manual + auto on data change threshold",
        operator_estimation_logic="Cardinality = row_count * selectivity",
        evidence=[]
    )
    assert stats.stats_source == "TableStatistics"
    assert stats.stats_granularity == StatsGranularity.COLUMN


def test_stats_granularities():
    """Stats granularity levels."""
    granularities = [
        StatsGranularity.TABLE,
        StatsGranularity.COLUMN,
        StatsGranularity.PARTITION,
        StatsGranularity.HISTOGRAM,
    ]
    assert len(granularities) == 4


def test_cost_model_creation():
    """CostModel must have dimensions."""
    cost = CostModel(
        cost_formula_location="src/optimizer/cost/cost_model.cpp",
        cost_dimensions=["cpu_cycles", "memory_bytes", "io_operations", "network_bytes"],
        operator_costs={
            "Scan": "io_cost + cpu_cost",
            "Join": "left_cost + right_cost + comparison_cost",
        },
        evidence=[]
    )
    assert len(cost.cost_dimensions) == 4
    assert "Scan" in cost.operator_costs


def test_cost_with_dimensions():
    """Cost can specify formula locations."""
    cost = CostModel(
        cost_formula_location="src/optimizer/cost/",
        cost_dimensions=["cpu", "io", "memory"],
        operator_costs={
            "Filter": "input_rows * cpu_per_row",
        },
        evidence=[
            Evidence(
                file_path="src/optimizer/cost/filter_cost.cpp",
                description="Filter operator cost formula"
            )
        ]
    )
    assert len(cost.evidence) == 1