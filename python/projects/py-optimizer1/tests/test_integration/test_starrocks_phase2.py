"""Phase 2 Integration Tests for StarRocks Optimizer Agents.

This module contains integration tests that exercise the specialized
agents against the StarRocks optimizer source code.
"""

import tempfile
from pathlib import Path

import pytest

from optimizer_analysis.agents.base import AgentResult
from optimizer_analysis.agents.rule_miner import RBOMinerAgent, CBOMinerAgent
from optimizer_analysis.agents.property_agent import PropertyAgent
from optimizer_analysis.agents.stats_cost_agent import StatsCostAgent
from optimizer_analysis.agents.observability_agent import ObservabilityAgent


# Constants for StarRocks paths
STARROCKS_PATH = "/home/lism/work/starrocks"
STARROCKS_OPTIMIZER_PATH = "/home/lism/work/starrocks/fe/fe-core/src/main/java/com/starrocks/sql/optimizer"


@pytest.fixture
def starrocks_exists():
    """Check if StarRocks source exists."""
    return Path(STARROCKS_PATH).exists()


@pytest.fixture
def starrocks_optimizer_path():
    """Return StarRocks optimizer path."""
    return STARROCKS_OPTIMIZER_PATH


class TestStarRocksPhase2RBO:
    """Test RBOMinerAgent against StarRocks transformation rules."""

    def test_rbo_miner_transformation_rules(self, starrocks_exists, starrocks_optimizer_path):
        """Test RBOMinerAgent scans StarRocks transformation rules directory."""
        if not starrocks_exists:
            pytest.skip(f"StarRocks source not found at {STARROCKS_PATH}")

        # Transformation rules path in StarRocks
        transformation_path = Path(starrocks_optimizer_path) / "rule" / "transformation"
        if not transformation_path.exists():
            pytest.skip(f"Transformation rules directory not found: {transformation_path}")

        with tempfile.TemporaryDirectory() as work_dir:
            agent = RBOMinerAgent(
                engine="StarRocks",
                work_dir=work_dir,
                source_path=str(transformation_path)
            )

            result = agent.execute()

            # Verify result structure
            assert isinstance(result, AgentResult)
            assert result.agent_name == "RBOMiner"
            assert result.status in ["success", "partial", "failed"]

            # Check that artifacts were created
            assert len(result.artifacts) > 0

            # Verify metadata contains expected fields
            assert "rules_found" in result.metadata
            assert "files_scanned" in result.metadata
            assert "category" in result.metadata

            # The transformation directory should have files
            assert result.metadata["files_scanned"] > 0

    def test_cbo_miner_implementation_rules(self, starrocks_exists, starrocks_optimizer_path):
        """Test CBOMinerAgent scans StarRocks implementation rules directory."""
        if not starrocks_exists:
            pytest.skip(f"StarRocks source not found at {STARROCKS_PATH}")

        # Implementation rules path in StarRocks
        implementation_path = Path(starrocks_optimizer_path) / "rule" / "implementation"
        if not implementation_path.exists():
            pytest.skip(f"Implementation rules directory not found: {implementation_path}")

        with tempfile.TemporaryDirectory() as work_dir:
            agent = CBOMinerAgent(
                engine="StarRocks",
                work_dir=work_dir,
                source_path=str(implementation_path)
            )

            result = agent.execute()

            # Verify result structure
            assert isinstance(result, AgentResult)
            assert result.agent_name == "CBOMiner"
            assert result.status in ["success", "partial", "failed"]

            # Check that artifacts were created
            assert len(result.artifacts) > 0

            # Verify metadata contains expected fields
            assert "rules_found" in result.metadata
            assert "files_scanned" in result.metadata
            assert "category" in result.metadata
            assert result.metadata["category"] == "cbo"

            # The implementation directory should have files
            assert result.metadata["files_scanned"] > 0


class TestStarRocksPhase2Property:
    """Test PropertyAgent against StarRocks property directory."""

    def test_property_agent_scan(self, starrocks_exists, starrocks_optimizer_path):
        """Test PropertyAgent scans StarRocks property directory."""
        if not starrocks_exists:
            pytest.skip(f"StarRocks source not found at {STARROCKS_PATH}")

        # Property path in StarRocks
        property_path = Path(starrocks_optimizer_path) / "property"
        if not property_path.exists():
            pytest.skip(f"Property directory not found: {property_path}")

        with tempfile.TemporaryDirectory() as work_dir:
            agent = PropertyAgent(
                engine="StarRocks",
                work_dir=work_dir,
                source_path=str(property_path)
            )

            result = agent.execute()

            # Verify result structure
            assert isinstance(result, AgentResult)
            assert result.agent_name == "PropertyAgent"
            assert result.status in ["success", "partial", "failed"]

            # Check that artifacts were created
            assert len(result.artifacts) > 0

            # Verify traits/index.json was created
            traits_index = Path(work_dir) / "traits" / "index.json"
            assert traits_index.exists()

            # Verify metadata contains expected fields
            assert "properties_found" in result.metadata
            assert "files_scanned" in result.metadata
            assert "confidence" in result.metadata

            # Property directory should have files
            assert result.metadata["files_scanned"] > 0


class TestStarRocksPhase2StatsCost:
    """Test StatsCostAgent against StarRocks stats/cost directories."""

    def test_stats_cost_agent_scan(self, starrocks_exists, starrocks_optimizer_path):
        """Test StatsCostAgent scans StarRocks statistics and cost directories."""
        if not starrocks_exists:
            pytest.skip(f"StarRocks source not found at {STARROCKS_PATH}")

        # Statistics and cost paths in StarRocks
        stats_path = Path(starrocks_optimizer_path) / "statistics"
        cost_path = Path(starrocks_optimizer_path) / "cost"

        if not stats_path.exists():
            pytest.skip(f"Statistics directory not found: {stats_path}")
        if not cost_path.exists():
            pytest.skip(f"Cost directory not found: {cost_path}")

        with tempfile.TemporaryDirectory() as work_dir:
            agent = StatsCostAgent(
                engine="StarRocks",
                work_dir=work_dir,
                stats_path=str(stats_path),
                cost_path=str(cost_path)
            )

            result = agent.execute()

            # Verify result structure
            assert isinstance(result, AgentResult)
            assert result.agent_name == "StatsCostAgent"
            assert result.status in ["success", "partial", "failed"]

            # Check that artifacts were created (stats/index.json and cost/index.json)
            assert len(result.artifacts) >= 2

            # Verify stats/index.json was created
            stats_index = Path(work_dir) / "stats" / "index.json"
            assert stats_index.exists()

            # Verify cost/index.json was created
            cost_index = Path(work_dir) / "cost" / "index.json"
            assert cost_index.exists()

            # Verify metadata contains expected fields
            assert "stats_found" in result.metadata
            assert "costs_found" in result.metadata

            # Statistics directory has many files
            assert result.metadata["stats_found"] > 0

            # Cost directory has files
            assert result.metadata["costs_found"] > 0


class TestStarRocksPhase2Observability:
    """Test ObservabilityAgent against StarRocks observability-related directories."""

    def test_observability_agent_scan(self, starrocks_exists, starrocks_optimizer_path):
        """Test ObservabilityAgent scans StarRocks optimizer for observability features."""
        if not starrocks_exists:
            pytest.skip(f"StarRocks source not found at {STARROCKS_PATH}")

        # Use the dump directory for observability testing
        # StarRocks has query dump, trace utilities in optimizer directory
        dump_path = Path(starrocks_optimizer_path) / "dump"
        if not dump_path.exists():
            pytest.skip(f"Dump directory not found: {dump_path}")

        with tempfile.TemporaryDirectory() as work_dir:
            agent = ObservabilityAgent(
                engine="StarRocks",
                work_dir=work_dir,
                source_path=str(dump_path)
            )

            result = agent.execute()

            # Verify result structure
            assert isinstance(result, AgentResult)
            assert result.agent_name == "ObservabilityAgent"
            assert result.status in ["success", "partial", "failed"]

            # Check that artifacts were created
            assert len(result.artifacts) > 0

            # Verify observability/index.json was created
            observability_index = Path(work_dir) / "observability" / "index.json"
            assert observability_index.exists()

            # Verify metadata contains expected fields
            assert "explain_interfaces_count" in result.metadata
            assert "trace_interfaces_count" in result.metadata
            assert "debug_hooks_count" in result.metadata
            assert "session_controls_count" in result.metadata
            assert "rule_fire_visibility" in result.metadata
            assert "memo_dump_support" in result.metadata


class TestStarRocksPhase2Structure:
    """Test StarRocks optimizer directory structure verification."""

    def test_starrocks_optimizer_structure_exists(self, starrocks_exists, starrocks_optimizer_path):
        """Verify StarRocks optimizer directory structure."""
        if not starrocks_exists:
            pytest.skip(f"StarRocks source not found at {STARROCKS_PATH}")

        optimizer_path = Path(starrocks_optimizer_path)
        assert optimizer_path.exists(), f"Optimizer directory not found: {optimizer_path}"

        # Check key directories exist
        assert (optimizer_path / "rule").exists()
        assert (optimizer_path / "property").exists()
        assert (optimizer_path / "statistics").exists()
        assert (optimizer_path / "cost").exists()

        # Check rule subdirectories
        rule_path = optimizer_path / "rule"
        assert (rule_path / "transformation").exists()
        assert (rule_path / "implementation").exists()

        # Check key files exist
        assert (optimizer_path / "Optimizer.java").exists()
        assert (optimizer_path / "Memo.java").exists()
        assert (optimizer_path / "Group.java").exists()
        assert (rule_path / "Rule.java").exists()
        assert (rule_path / "RuleSet.java").exists()
        assert (rule_path / "RuleType.java").exists()

    def test_starrocks_has_key_rule_files(self, starrocks_exists, starrocks_optimizer_path):
        """Verify StarRocks has expected rule-related files."""
        if not starrocks_exists:
            pytest.skip(f"StarRocks source not found at {STARROCKS_PATH}")

        rule_path = Path(starrocks_optimizer_path) / "rule"
        assert rule_path.exists()

        # Check for specific important files
        expected_files = [
            "Rule.java",
            "RuleSet.java",
            "RuleType.java",
            "Binder.java"
        ]

        for filename in expected_files:
            file_path = rule_path / filename
            assert file_path.exists(), f"Expected file not found: {file_path}"

    def test_starrocks_has_stats_and_cost_files(self, starrocks_exists, starrocks_optimizer_path):
        """Verify StarRocks has expected statistics and cost files."""
        if not starrocks_exists:
            pytest.skip(f"StarRocks source not found at {STARROCKS_PATH}")

        stats_path = Path(starrocks_optimizer_path) / "statistics"
        cost_path = Path(starrocks_optimizer_path) / "cost"

        assert stats_path.exists()
        assert cost_path.exists()

        # Check for specific statistics files
        expected_stats_files = [
            "Statistics.java",
            "StatisticsCalculator.java",
            "ColumnStatistic.java"
        ]
        for filename in expected_stats_files:
            file_path = stats_path / filename
            assert file_path.exists(), f"Expected stats file not found: {file_path}"

        # Check for specific cost files
        expected_cost_files = [
            "CostModel.java",
            "CostEstimate.java"
        ]
        for filename in expected_cost_files:
            file_path = cost_path / filename
            assert file_path.exists(), f"Expected cost file not found: {file_path}"