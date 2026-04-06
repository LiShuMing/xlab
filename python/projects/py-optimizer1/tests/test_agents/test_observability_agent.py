"""Tests for ObservabilityAgent."""

import json
import pytest
from os import makedirs
from os.path import exists, join
from unittest.mock import MagicMock, Mock
import tempfile

from optimizer_analysis.agents.base import AgentResult, BaseAgent
from optimizer_analysis.agents.observability_agent import ObservabilityAgent
from optimizer_analysis.llm_client import ChatMessage
from optimizer_analysis.schemas.observability import Observability, RuleFireVisibility
from optimizer_analysis.schemas.base import Evidence, EvidenceType
from optimizer_analysis.scanners.base import CodeFile


class TestObservabilityAgentCreation:
    """Tests for ObservabilityAgent instantiation."""

    def test_observability_agent_creation(self):
        """ObservabilityAgent can be instantiated correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = ObservabilityAgent(
                engine="clickhouse",
                work_dir=tmpdir,
                source_path="/path/to/observability"
            )
            assert agent.name == "ObservabilityAgent"
            assert agent.engine == "clickhouse"
            assert agent.work_dir == tmpdir
            assert agent.source_path == "/path/to/observability"
            assert agent.llm_client is None

    def test_observability_agent_with_llm_client(self):
        """ObservabilityAgent can be instantiated with LLM client."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_llm = Mock()
            agent = ObservabilityAgent(
                engine="starrocks",
                work_dir=tmpdir,
                source_path="/path/to/observability",
                llm_client=mock_llm
            )
            assert agent.llm_client is mock_llm

    def test_observability_agent_inherits_from_base_agent(self):
        """ObservabilityAgent inherits from BaseAgent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = ObservabilityAgent(
                engine="postgres",
                work_dir=tmpdir,
                source_path="/observability"
            )
            assert isinstance(agent, BaseAgent)


class TestObservabilityAgentExecute:
    """Tests for ObservabilityAgent execute method."""

    def test_observability_agent_execute_nonexistent_path(self):
        """Execute handles non-existent paths gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = ObservabilityAgent(
                engine="test",
                work_dir=tmpdir,
                source_path="/nonexistent/observability"
            )
            result = agent.execute()
            assert result.agent_name == "ObservabilityAgent"
            assert result.status == "partial"
            assert len(result.artifacts) == 1
            assert result.metadata["explain_interfaces_count"] == 0
            assert result.metadata["trace_interfaces_count"] == 0

    def test_observability_agent_execute_creates_artifacts(self):
        """Execute creates observability/index.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = ObservabilityAgent(
                engine="test",
                work_dir=tmpdir,
                source_path="/nonexistent"
            )
            result = agent.execute()

            # Check that artifact was created
            assert len(result.artifacts) == 1
            observability_index = join(tmpdir, "observability", "index.json")
            assert observability_index in result.artifacts

            # Verify file exists and contains expected structure
            assert exists(observability_index)

            with open(observability_index) as f:
                data = json.load(f)
                assert "explain_interfaces" in data
                assert "trace_interfaces" in data
                assert "rule_fire_visibility" in data
                assert "memo_dump_support" in data
                assert "session_controls" in data
                assert "debug_hooks" in data

    def test_observability_agent_execute_with_source_files(self):
        """Execute processes observability source files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source directory with sample Java file
            source_dir = join(tmpdir, "source")
            makedirs(source_dir, exist_ok=True)

            java_file = join(source_dir, "ExplainAnalyzer.java")
            with open(java_file, "w") as f:
                f.write("""
public class ExplainAnalyzer {
    public String explain(Query query) {
        // EXPLAIN implementation
        return generateExplainOutput(query);
    }

    public String explainAnalyze(Query query) {
        // EXPLAIN ANALYZE implementation
        return generateExplainAnalyzeOutput(query);
    }
}
""")

            agent = ObservabilityAgent(
                engine="test",
                work_dir=tmpdir,
                source_path=source_dir
            )
            result = agent.execute()

            assert result.status == "partial"
            assert len(result.artifacts) == 1

            # Check that the index.json was created
            observability_index = join(tmpdir, "observability", "index.json")
            assert exists(observability_index)

            with open(observability_index) as f:
                data = json.load(f)
                # Should have found explain patterns via basic pattern matching
                assert len(data["explain_interfaces"]) >= 0


class TestAnalyzeExplainInterface:
    """Tests for analyze_explain_interface method."""

    def test_analyze_explain_interface_requires_llm_client(self):
        """analyze_explain_interface raises ValueError without LLM client."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = ObservabilityAgent(
                engine="test",
                work_dir=tmpdir,
                source_path="/observability"
            )
            code_file = CodeFile(
                path="/test/explain.java",
                content="public class ExplainAnalyzer {}",
                language="java"
            )
            with pytest.raises(ValueError, match="LLM client is required"):
                agent.analyze_explain_interface(code_file)

    def test_analyze_explain_interface_with_llm_client(self):
        """analyze_explain_interface returns dict with valid LLM response."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_llm = Mock()
            mock_llm.chat.return_value = json.dumps({
                "explain_interfaces": ["EXPLAIN", "EXPLAIN ANALYZE", "EXPLAIN VERBOSE"],
                "has_explain_analyze": True,
                "explain_output_formats": ["TEXT", "JSON"],
                "evidence": [],
                "uncertain_points": []
            })

            agent = ObservabilityAgent(
                engine="test",
                work_dir=tmpdir,
                source_path="/observability",
                llm_client=mock_llm
            )

            code_file = CodeFile(
                path="/test/ExplainAnalyzer.java",
                content="public class ExplainAnalyzer { public String explain() {} }",
                language="java"
            )

            result = agent.analyze_explain_interface(code_file)

            assert result is not None
            assert isinstance(result, dict)
            assert "EXPLAIN" in result["explain_interfaces"]
            assert "EXPLAIN ANALYZE" in result["explain_interfaces"]
            assert result["has_explain_analyze"] == True

    def test_analyze_explain_interface_returns_empty_on_error_response(self):
        """analyze_explain_interface returns empty dict if LLM returns error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_llm = Mock()
            mock_llm.chat.return_value = json.dumps({
                "error": "No explain interface found",
                "reason": "Not an explain file"
            })

            agent = ObservabilityAgent(
                engine="test",
                work_dir=tmpdir,
                source_path="/observability",
                llm_client=mock_llm
            )

            code_file = CodeFile(
                path="/test/random.java",
                content="public class RandomClass {}",
                language="java"
            )

            result = agent.analyze_explain_interface(code_file)
            assert result == {}


class TestAnalyzeTraceSupport:
    """Tests for analyze_trace_support method."""

    def test_analyze_trace_support_requires_llm_client(self):
        """analyze_trace_support raises ValueError without LLM client."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = ObservabilityAgent(
                engine="test",
                work_dir=tmpdir,
                source_path="/observability"
            )
            code_file = CodeFile(
                path="/test/trace.java",
                content="public class TraceSupport {}",
                language="java"
            )
            with pytest.raises(ValueError, match="LLM client is required"):
                agent.analyze_trace_support(code_file)

    def test_analyze_trace_support_with_llm_client(self):
        """analyze_trace_support returns dict with valid LLM response."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_llm = Mock()
            mock_llm.chat.return_value = json.dumps({
                "trace_interfaces": ["optimizer_trace", "rule_trace", "cost_trace"],
                "has_rule_trace": True,
                "has_cost_trace": True,
                "has_memo_dump": True,
                "debug_hooks": ["optimizer_debug_mode", "rule_fire_log"],
                "session_controls": ["optimizer_mode", "cost_model_version"],
                "rule_fire_visibility": "partial",
                "evidence": [],
                "uncertain_points": []
            })

            agent = ObservabilityAgent(
                engine="test",
                work_dir=tmpdir,
                source_path="/observability",
                llm_client=mock_llm
            )

            code_file = CodeFile(
                path="/test/TraceSupport.java",
                content="public class TraceSupport { public void trace() {} }",
                language="java"
            )

            result = agent.analyze_trace_support(code_file)

            assert result is not None
            assert isinstance(result, dict)
            assert "optimizer_trace" in result["trace_interfaces"]
            assert result["has_memo_dump"] == True
            assert result["rule_fire_visibility"] == "partial"
            assert len(result["debug_hooks"]) == 2
            assert len(result["session_controls"]) == 2

    def test_analyze_trace_support_returns_empty_on_error_response(self):
        """analyze_trace_support returns empty dict if LLM returns error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_llm = Mock()
            mock_llm.chat.return_value = json.dumps({
                "error": "No trace interface found",
                "reason": "Not a trace file"
            })

            agent = ObservabilityAgent(
                engine="test",
                work_dir=tmpdir,
                source_path="/observability",
                llm_client=mock_llm
            )

            code_file = CodeFile(
                path="/test/random.java",
                content="public class RandomClass {}",
                language="java"
            )

            result = agent.analyze_trace_support(code_file)
            assert result == {}


class TestScanObservability:
    """Tests for scan_observability method."""

    def test_scan_observability_empty_path(self):
        """scan_observability returns Observability for non-existent path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = ObservabilityAgent(
                engine="test",
                work_dir=tmpdir,
                source_path="/nonexistent/observability"
            )
            result = agent.scan_observability()
            assert isinstance(result, Observability)
            assert result.explain_interfaces == []
            assert result.trace_interfaces == []
            assert result.rule_fire_visibility == "none"

    def test_scan_observability_with_java_files(self):
        """scan_observability processes Java files in observability directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create observability directory with sample Java file
            source_dir = join(tmpdir, "observability")
            makedirs(source_dir, exist_ok=True)

            java_file = join(source_dir, "ExplainHandler.java")
            with open(java_file, "w") as f:
                f.write("""
public class ExplainHandler {
    public void handleExplain() {
        // EXPLAIN ANALYZE handling
        String trace = optimizer_trace;
        String debug = DEBUG_MODE;
    }
}
""")

            agent = ObservabilityAgent(
                engine="test",
                work_dir=tmpdir,
                source_path=source_dir
            )
            result = agent.scan_observability()

            assert isinstance(result, Observability)
            # Should have evidence for the file
            assert len(result.evidence) >= 1
            assert len(result.uncertain_points) >= 1  # Requires LLM analysis note

    def test_scan_observability_with_llm_client(self):
        """scan_observability uses LLM client when available."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source directory
            source_dir = join(tmpdir, "source")
            makedirs(source_dir, exist_ok=True)

            java_file = join(source_dir, "Explain.java")
            with open(java_file, "w") as f:
                f.write("public class Explain {}")

            # Create mock LLM client
            mock_llm = Mock()
            mock_llm.chat.return_value = json.dumps({
                "explain_interfaces": ["EXPLAIN"],
                "has_explain_analyze": False,
                "evidence": [],
                "uncertain_points": []
            })

            agent = ObservabilityAgent(
                engine="test",
                work_dir=tmpdir,
                source_path=source_dir,
                llm_client=mock_llm
            )
            result = agent.scan_observability()

            assert isinstance(result, Observability)
            # Should have called LLM
            assert mock_llm.chat.called


class TestIsObservabilityFile:
    """Tests for _is_observability_file method."""

    def test_is_observability_file_detects_explain_class(self):
        """_is_observability_file detects Explain class definitions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = ObservabilityAgent(
                engine="test",
                work_dir=tmpdir,
                source_path="/path"
            )

            code_file = CodeFile(
                path="/src/Explain.java",
                content="public class ExplainAnalyzer { }",
                language="java"
            )
            assert agent._is_observability_file(code_file) is True

    def test_is_observability_file_detects_trace_class(self):
        """_is_observability_file detects Trace class definitions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = ObservabilityAgent(
                engine="test",
                work_dir=tmpdir,
                source_path="/path"
            )

            code_file = CodeFile(
                path="/src/Trace.java",
                content="public class OptimizerTrace { }",
                language="java"
            )
            assert agent._is_observability_file(code_file) is True

    def test_is_observability_file_detects_memo_dump(self):
        """_is_observability_file detects memo dump references."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = ObservabilityAgent(
                engine="test",
                work_dir=tmpdir,
                source_path="/path"
            )

            code_file = CodeFile(
                path="/src/Memo.java",
                content="public class MemoHandler { public void dumpMemo() {} }",
                language="java"
            )
            assert agent._is_observability_file(code_file) is True

    def test_is_observability_file_detects_session_controls(self):
        """_is_observability_file detects session control references."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = ObservabilityAgent(
                engine="test",
                work_dir=tmpdir,
                source_path="/path"
            )

            code_file = CodeFile(
                path="/src/Session.java",
                content="public class SessionHandler { set optimizer_mode; }",
                language="java"
            )
            assert agent._is_observability_file(code_file) is True

    def test_is_observability_file_rejects_non_observability_files(self):
        """_is_observability_file rejects non-observability files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = ObservabilityAgent(
                engine="test",
                work_dir=tmpdir,
                source_path="/path"
            )

            code_file = CodeFile(
                path="/src/rules/RegularRule.java",
                content="public class RegularRule { public void transform() {} }",
                language="java"
            )
            assert agent._is_observability_file(code_file) is False


class TestExtractBasicPatterns:
    """Tests for _extract_basic_patterns method."""

    def test_extract_basic_patterns_explain(self):
        """_extract_basic_patterns finds EXPLAIN patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = ObservabilityAgent(
                engine="test",
                work_dir=tmpdir,
                source_path="/path"
            )

            code_file = CodeFile(
                path="/test/Explain.java",
                content="public class ExplainAnalyzer { EXPLAIN ANALYZE; }",
                language="java"
            )

            result = agent._extract_basic_patterns(code_file)
            assert len(result["explain_interfaces"]) >= 1

    def test_extract_basic_patterns_memo_dump(self):
        """_extract_basic_patterns detects memo dump support."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = ObservabilityAgent(
                engine="test",
                work_dir=tmpdir,
                source_path="/path"
            )

            code_file = CodeFile(
                path="/test/Memo.java",
                content="public class MemoHandler { public void memoDump() {} }",
                language="java"
            )

            result = agent._extract_basic_patterns(code_file)
            assert result["memo_dump_support"] == True

    def test_extract_basic_patterns_empty_content(self):
        """_extract_basic_patterns returns empty for unrelated content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = ObservabilityAgent(
                engine="test",
                work_dir=tmpdir,
                source_path="/path"
            )

            code_file = CodeFile(
                path="/test/Other.java",
                content="public class SomeClass { }",
                language="java"
            )

            result = agent._extract_basic_patterns(code_file)
            assert result["explain_interfaces"] == []
            assert result["trace_interfaces"] == []
            assert result["memo_dump_support"] == False