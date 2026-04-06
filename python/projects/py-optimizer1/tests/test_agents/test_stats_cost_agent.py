"""Tests for StatsCostAgent."""

import json
import pytest
from os import makedirs
from os.path import exists, join
from unittest.mock import MagicMock, Mock
import tempfile

from optimizer_analysis.agents.base import AgentResult, BaseAgent
from optimizer_analysis.agents.stats_cost_agent import StatsCostAgent
from optimizer_analysis.llm_client import ChatMessage
from optimizer_analysis.schemas.stats_cost import CostModel, StatisticsInfo, StatsGranularity
from optimizer_analysis.schemas.base import Evidence, EvidenceType
from optimizer_analysis.scanners.base import CodeFile


class TestStatsCostAgentCreation:
    """Tests for StatsCostAgent instantiation."""

    def test_stats_cost_agent_creation(self):
        """StatsCostAgent can be instantiated correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = StatsCostAgent(
                engine="clickhouse",
                work_dir=tmpdir,
                stats_path="/path/to/stats",
                cost_path="/path/to/cost"
            )
            assert agent.name == "StatsCostAgent"
            assert agent.engine == "clickhouse"
            assert agent.work_dir == tmpdir
            assert agent.stats_path == "/path/to/stats"
            assert agent.cost_path == "/path/to/cost"
            assert agent.llm_client is None

    def test_stats_cost_agent_with_llm_client(self):
        """StatsCostAgent can be instantiated with LLM client."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_llm = Mock()
            agent = StatsCostAgent(
                engine="starrocks",
                work_dir=tmpdir,
                stats_path="/path/to/stats",
                cost_path="/path/to/cost",
                llm_client=mock_llm
            )
            assert agent.llm_client is mock_llm

    def test_stats_cost_agent_inherits_from_base_agent(self):
        """StatsCostAgent inherits from BaseAgent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = StatsCostAgent(
                engine="postgres",
                work_dir=tmpdir,
                stats_path="/stats",
                cost_path="/cost"
            )
            assert isinstance(agent, BaseAgent)


class TestStatsCostAgentExecute:
    """Tests for StatsCostAgent execute method."""

    def test_stats_cost_agent_execute_nonexistent_paths(self):
        """Execute handles non-existent paths gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = StatsCostAgent(
                engine="test",
                work_dir=tmpdir,
                stats_path="/nonexistent/stats",
                cost_path="/nonexistent/cost"
            )
            result = agent.execute()
            assert result.agent_name == "StatsCostAgent"
            assert result.status == "partial"
            assert len(result.artifacts) == 2
            assert result.metadata["stats_found"] == 0
            assert result.metadata["costs_found"] == 0

    def test_stats_cost_agent_execute_creates_artifacts(self):
        """Execute creates stats/index.json and cost/index.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = StatsCostAgent(
                engine="test",
                work_dir=tmpdir,
                stats_path="/nonexistent",
                cost_path="/nonexistent"
            )
            result = agent.execute()

            # Check that artifacts were created
            assert len(result.artifacts) == 2
            stats_index = join(tmpdir, "stats", "index.json")
            cost_index = join(tmpdir, "cost", "index.json")
            assert stats_index in result.artifacts
            assert cost_index in result.artifacts

            # Verify files exist and contain expected structure
            assert exists(stats_index)
            assert exists(cost_index)

            with open(stats_index) as f:
                stats_data = json.load(f)
                assert stats_data["engine"] == "test"
                assert "stats_found" in stats_data
                assert "statistics" in stats_data

            with open(cost_index) as f:
                cost_data = json.load(f)
                assert cost_data["engine"] == "test"
                assert "costs_found" in cost_data
                assert "cost_models" in cost_data


class TestAnalyzeStatistics:
    """Tests for analyze_statistics method."""

    def test_analyze_statistics_requires_llm_client(self):
        """analyze_statistics raises ValueError without LLM client."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = StatsCostAgent(
                engine="test",
                work_dir=tmpdir,
                stats_path="/stats",
                cost_path="/cost"
            )
            code_file = CodeFile(
                path="/test/stats.java",
                content="public class Statistics {}",
                language="java"
            )
            with pytest.raises(ValueError, match="LLM client is required"):
                agent.analyze_statistics(code_file)

    def test_analyze_statistics_with_llm_client(self):
        """analyze_statistics returns StatisticsInfo with valid LLM response."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create mock LLM client
            mock_llm = Mock()
            mock_llm.chat.return_value = json.dumps({
                "stats_source": "AnalyzeCommand",
                "stats_objects": ["ndv", "row_count", "histogram"],
                "stats_granularity": "column",
                "storage_location": "Memory cache",
                "collection_trigger": "Manual ANALYZE",
                "operator_estimation_logic": "row_count * selectivity",
                "evidence": []
            })

            agent = StatsCostAgent(
                engine="test",
                work_dir=tmpdir,
                stats_path="/stats",
                cost_path="/cost",
                llm_client=mock_llm
            )

            code_file = CodeFile(
                path="/test/Statistics.java",
                content="public class StatisticsCollector {}",
                language="java"
            )

            result = agent.analyze_statistics(code_file)

            assert result is not None
            assert isinstance(result, StatisticsInfo)
            assert result.stats_source == "AnalyzeCommand"
            assert "ndv" in result.stats_objects
            assert result.stats_granularity == StatsGranularity.COLUMN

    def test_analyze_statistics_returns_none_on_error_response(self):
        """analyze_statistics returns None if LLM returns error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_llm = Mock()
            mock_llm.chat.return_value = json.dumps({
                "error": "No statistics info found",
                "reason": "Not a statistics file"
            })

            agent = StatsCostAgent(
                engine="test",
                work_dir=tmpdir,
                stats_path="/stats",
                cost_path="/cost",
                llm_client=mock_llm
            )

            code_file = CodeFile(
                path="/test/random.java",
                content="public class RandomClass {}",
                language="java"
            )

            result = agent.analyze_statistics(code_file)
            assert result is None


class TestAnalyzeCostModel:
    """Tests for analyze_cost_model method."""

    def test_analyze_cost_model_requires_llm_client(self):
        """analyze_cost_model raises ValueError without LLM client."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = StatsCostAgent(
                engine="test",
                work_dir=tmpdir,
                stats_path="/stats",
                cost_path="/cost"
            )
            code_file = CodeFile(
                path="/test/cost.java",
                content="public class CostModel {}",
                language="java"
            )
            with pytest.raises(ValueError, match="LLM client is required"):
                agent.analyze_cost_model(code_file)

    def test_analyze_cost_model_with_llm_client(self):
        """analyze_cost_model returns CostModel with valid LLM response."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_llm = Mock()
            mock_llm.chat.return_value = json.dumps({
                "cost_formula_location": "src/optimizer/cost/",
                "cost_dimensions": ["cpu", "io", "memory"],
                "operator_costs": {
                    "Scan": "io_cost",
                    "Join": "left_cost + right_cost"
                },
                "evidence": []
            })

            agent = StatsCostAgent(
                engine="test",
                work_dir=tmpdir,
                stats_path="/stats",
                cost_path="/cost",
                llm_client=mock_llm
            )

            code_file = CodeFile(
                path="/test/CostModel.java",
                content="public class CostCalculator {}",
                language="java"
            )

            result = agent.analyze_cost_model(code_file)

            assert result is not None
            assert isinstance(result, CostModel)
            assert result.cost_formula_location == "src/optimizer/cost/"
            assert "cpu" in result.cost_dimensions
            assert "Scan" in result.operator_costs

    def test_analyze_cost_model_returns_none_on_error_response(self):
        """analyze_cost_model returns None if LLM returns error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_llm = Mock()
            mock_llm.chat.return_value = json.dumps({
                "error": "No cost info found",
                "reason": "Not a cost file"
            })

            agent = StatsCostAgent(
                engine="test",
                work_dir=tmpdir,
                stats_path="/stats",
                cost_path="/cost",
                llm_client=mock_llm
            )

            code_file = CodeFile(
                path="/test/random.java",
                content="public class RandomClass {}",
                language="java"
            )

            result = agent.analyze_cost_model(code_file)
            assert result is None


class TestScanStatistics:
    """Tests for scan_statistics method."""

    def test_scan_statistics_empty_path(self):
        """scan_statistics returns empty list for non-existent path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = StatsCostAgent(
                engine="test",
                work_dir=tmpdir,
                stats_path="/nonexistent/stats",
                cost_path="/cost"
            )
            results = agent.scan_statistics()
            assert results == []

    def test_scan_statistics_with_java_files(self):
        """scan_statistics processes Java files in stats directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create stats directory with sample Java file
            stats_dir = join(tmpdir, "stats")
            makedirs(stats_dir, exist_ok=True)
            java_file = join(stats_dir, "StatisticsCollector.java")
            with open(java_file, "w") as f:
                f.write("""
public class StatisticsCollector {
    public void collectStatistics() {
        // Collect NDV, row count, histogram
        long ndv = calculateNDV();
        long rowCount = getRowCount();
    }
}
""")

            agent = StatsCostAgent(
                engine="test",
                work_dir=tmpdir,
                stats_path=stats_dir,
                cost_path="/cost"
            )
            results = agent.scan_statistics()

            # Should return a placeholder result without LLM
            assert len(results) >= 1
            assert isinstance(results[0], StatisticsInfo)


class TestScanCostModels:
    """Tests for scan_cost_models method."""

    def test_scan_cost_models_empty_path(self):
        """scan_cost_models returns empty list for non-existent path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = StatsCostAgent(
                engine="test",
                work_dir=tmpdir,
                stats_path="/stats",
                cost_path="/nonexistent/cost"
            )
            results = agent.scan_cost_models()
            assert results == []

    def test_scan_cost_models_with_java_files(self):
        """scan_cost_models processes Java files in cost directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create cost directory with sample Java file
            cost_dir = join(tmpdir, "cost")
            makedirs(cost_dir, exist_ok=True)
            java_file = join(cost_dir, "CostCalculator.java")
            with open(java_file, "w") as f:
                f.write("""
public class CostCalculator {
    public double computeCost() {
        // Calculate CPU cost and IO cost
        double cpuCost = estimateCpuCost();
        double ioCost = estimateIoCost();
        return cpuCost + ioCost;
    }
}
""")

            agent = StatsCostAgent(
                engine="test",
                work_dir=tmpdir,
                stats_path="/stats",
                cost_path=cost_dir
            )
            results = agent.scan_cost_models()

            # Should return a placeholder result without LLM
            assert len(results) >= 1
            assert isinstance(results[0], CostModel)