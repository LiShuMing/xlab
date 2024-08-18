"""Tests for Rule Miner Agent and RuleMiningResult model."""

import json
import pytest
from os import makedirs
from os.path import exists, join
from unittest.mock import MagicMock, Mock

from optimizer_analysis.agents.base import AgentResult, BaseAgent
from optimizer_analysis.agents.rule_miner import (
    CBOMinerAgent,
    PostOptimizerMinerAgent,
    RBOMinerAgent,
    RuleMiningResult,
    RuleMinerAgent,
    ScalarRuleMinerAgent,
)
from optimizer_analysis.llm_client import ChatMessage
from optimizer_analysis.schemas.rule import Rule, RuleCategory, ImplementationType
from optimizer_analysis.schemas.base import Evidence, EvidenceType
from optimizer_analysis.scanners.base import CodeFile


class TestRuleMiningResult:
    """Tests for RuleMiningResult model."""

    def test_rule_mining_result_creation(self):
        """RuleMiningResult basic creation with required fields."""
        result = RuleMiningResult(
            engine="clickhouse",
            category=RuleCategory.RBO,
            rules_found=2,
            rules=[
                Rule(
                    rule_id="R001",
                    rule_name="PushDownFilter",
                    engine="clickhouse",
                    rule_category=RuleCategory.RBO
                ),
                Rule(
                    rule_id="R002",
                    rule_name="MergeProjection",
                    engine="clickhouse",
                    rule_category=RuleCategory.RBO
                )
            ],
            confidence="medium",
            notes=["Initial analysis", "Requires manual review"]
        )
        assert result.engine == "clickhouse"
        assert result.category == RuleCategory.RBO
        assert result.rules_found == 2
        assert len(result.rules) == 2
        assert result.confidence == "medium"
        assert len(result.notes) == 2
        assert "Initial analysis" in result.notes

    def test_rule_mining_result_with_empty_rules(self):
        """RuleMiningResult with no rules found."""
        result = RuleMiningResult(
            engine="starrocks",
            category=RuleCategory.CBO,
            rules_found=0,
            rules=[],
            confidence="low",
            notes=["No rules found in source"]
        )
        assert result.engine == "starrocks"
        assert result.category == RuleCategory.CBO
        assert result.rules_found == 0
        assert result.rules == []
        assert result.confidence == "low"

    def test_rule_mining_result_all_categories(self):
        """RuleMiningResult works with all RuleCategory values."""
        for category in [RuleCategory.RBO, RuleCategory.CBO, RuleCategory.SCALAR,
                         RuleCategory.POST_OPT, RuleCategory.IMPLICIT]:
            result = RuleMiningResult(
                engine="test",
                category=category,
                rules_found=0,
                rules=[],
                confidence="unknown"
            )
            assert result.category == category

    def test_rule_mining_result_json_serialization(self):
        """RuleMiningResult can be serialized to JSON."""
        result = RuleMiningResult(
            engine="postgres",
            category=RuleCategory.SCALAR,
            rules_found=1,
            rules=[
                Rule(
                    rule_id="S001",
                    rule_name="ScalarSubqueryElimination",
                    engine="postgres",
                    rule_category=RuleCategory.SCALAR
                )
            ],
            confidence="high",
            notes=["Verified rule"]
        )
        json_str = result.model_dump_json(indent=2)
        data = json.loads(json_str)
        assert data["engine"] == "postgres"
        assert data["category"] == "scalar"
        assert data["rules_found"] == 1
        assert data["confidence"] == "high"
        assert len(data["rules"]) == 1
        assert data["rules"][0]["rule_id"] == "S001"


class TestRuleMinerAgent:
    """Tests for RuleMinerAgent class."""

    def test_rule_miner_agent_creation(self):
        """RuleMinerAgent can be instantiated correctly."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = RuleMinerAgent(
                engine="clickhouse",
                work_dir=tmpdir,
                category=RuleCategory.RBO,
                source_path="/path/to/rules"
            )
            assert agent.name == "RuleMiner"
            assert agent.engine == "clickhouse"
            assert agent.work_dir == tmpdir
            assert agent.category == RuleCategory.RBO
            assert agent.source_path == "/path/to/rules"
            assert agent.llm_client is None

    def test_rule_miner_agent_with_llm_client(self):
        """RuleMinerAgent can be instantiated with LLM client."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_llm = object()  # Mock LLM client
            agent = RuleMinerAgent(
                engine="starrocks",
                work_dir=tmpdir,
                category=RuleCategory.CBO,
                source_path="/path/to/cbo",
                llm_client=mock_llm
            )
            assert agent.llm_client is mock_llm

    def test_rule_miner_agent_inherits_from_base_agent(self):
        """RuleMinerAgent inherits from BaseAgent."""
        from optimizer_analysis.agents.base import BaseAgent

        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = RuleMinerAgent(
                engine="test",
                work_dir=tmpdir,
                category=RuleCategory.RBO,
                source_path="/test"
            )
            assert isinstance(agent, BaseAgent)

    def test_rule_miner_agent_execute_returns_partial_status(self):
        """RuleMinerAgent execute returns AgentResult with needs_manual_review."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = RuleMinerAgent(
                engine="clickhouse",
                work_dir=join(tmpdir, "work"),
                category=RuleCategory.RBO,
                source_path="/path/to/rules"
            )
            result = agent.execute()

            assert isinstance(result, AgentResult)
            assert result.agent_name == "RuleMiner"
            assert result.status == "partial"
            assert result.metadata["needs_manual_review"] is True
            assert "confidence" in result.metadata

    def test_rule_miner_agent_execute_creates_artifact(self):
        """RuleMinerAgent creates rules artifact file."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = join(tmpdir, "work")
            agent = RuleMinerAgent(
                engine="starrocks",
                work_dir=work_dir,
                category=RuleCategory.CBO,
                source_path="/path/to/cbo_rules"
            )
            result = agent.execute()

            # Check artifact file was created
            assert len(result.artifacts) == 1
            artifact_path = result.artifacts[0]
            assert exists(artifact_path)
            assert artifact_path.endswith("rules.json")

            # Verify JSON content
            with open(artifact_path, "r") as f:
                data = json.load(f)

            assert data["engine"] == "starrocks"
            assert data["category"] == "cbo"
            assert data["rules_found"] == 0
            assert data["confidence"] == "low"

    def test_rule_miner_agent_execute_different_categories(self):
        """RuleMinerAgent works with different rule categories."""
        import tempfile

        categories = [
            RuleCategory.RBO,
            RuleCategory.CBO,
            RuleCategory.SCALAR,
            RuleCategory.POST_OPT,
            RuleCategory.IMPLICIT
        ]

        for category in categories:
            with tempfile.TemporaryDirectory() as tmpdir:
                agent = RuleMinerAgent(
                    engine="test",
                    work_dir=tmpdir,
                    category=category,
                    source_path="/test"
                )
                result = agent.execute()

                assert result.status == "partial"
                assert result.metadata["category"] == category.value

    def test_rule_miner_agent_creates_rules_directory(self):
        """RuleMinerAgent creates rules subdirectory for artifacts."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = join(tmpdir, "work")
            agent = RuleMinerAgent(
                engine="postgres",
                work_dir=work_dir,
                category=RuleCategory.POST_OPT,
                source_path="/path/to/post_opt"
            )
            result = agent.execute()

            # Check that rules directory was created
            rules_dir = join(work_dir, "rules")
            assert exists(rules_dir)

    def test_rule_miner_agent_includes_source_path_in_notes(self):
        """RuleMinerAgent includes source_path in analysis notes."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = RuleMinerAgent(
                engine="clickhouse",
                work_dir=join(tmpdir, "work"),
                category=RuleCategory.RBO,
                source_path="/clickhouse/src/optimizer/rules"
            )
            result = agent.execute()

            # Verify notes contain source_path
            artifact_path = result.artifacts[0]
            with open(artifact_path, "r") as f:
                data = json.load(f)

            assert any("/clickhouse/src/optimizer/rules" in note for note in data["notes"])

    def test_rule_miner_agent_artifact_path(self):
        """RuleMinerAgent _artifact_path generates correct paths."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = RuleMinerAgent(
                engine="test",
                work_dir=tmpdir,
                category=RuleCategory.RBO,
                source_path="/test"
            )
            path = agent._artifact_path("rules.json")
            assert path == join(tmpdir, "rules.json")


class TestRuleMinerExtractRuleFromCode:
    """Tests for RuleMinerAgent extract_rule_from_code method."""

    def test_extract_rule_from_code_requires_llm_client(self):
        """extract_rule_from_code raises error without LLM client."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = RuleMinerAgent(
                engine="clickhouse",
                work_dir=tmpdir,
                category=RuleCategory.RBO,
                source_path="/test"
            )

            code_file = CodeFile(
                path="/test/Rule.java",
                content="public class Rule {}",
                language="java"
            )

            with pytest.raises(ValueError, match="LLM client"):
                agent.extract_rule_from_code(code_file)

    def test_extract_rule_from_code_with_mocked_llm(self):
        """extract_rule_from_code works with mocked LLM client."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create mock LLM client
            mock_llm = Mock()
            mock_response = json.dumps({
                "rule_id": "R001",
                "rule_name": "PushDownFilter",
                "rule_category": "rbo",
                "implementation_type": "explicitly_implemented",
                "lifecycle_stage": "logical_optimization",
                "source_files": ["FilterPushdownRule.java"],
                "transformation_logic": "Pushes filter predicates down to scan",
                "input_operators": ["Filter", "Scan"],
                "output_operators": ["Scan"],
                "depends_on_stats": False,
                "depends_on_cost": False,
                "depends_on_property": False,
                "confidence": "high",
                "evidence": [
                    {
                        "file_path": "/test/FilterPushdownRule.java",
                        "description": "Rule implementation",
                        "line_start": 10,
                        "line_end": 50,
                        "evidence_type": "source_code"
                    }
                ]
            })
            mock_llm.chat = Mock(return_value=mock_response)

            agent = RuleMinerAgent(
                engine="clickhouse",
                work_dir=tmpdir,
                category=RuleCategory.RBO,
                source_path="/test",
                llm_client=mock_llm
            )

            code_file = CodeFile(
                path="/test/FilterPushdownRule.java",
                content="public class FilterPushdownRule implements Rule { }",
                language="java"
            )

            rule = agent.extract_rule_from_code(code_file)

            assert rule is not None
            assert rule.rule_id == "R001"
            assert rule.rule_name == "PushDownFilter"
            assert rule.engine == "clickhouse"
            assert rule.rule_category == RuleCategory.RBO
            assert rule.implementation_type == ImplementationType.EXPLICIT
            assert len(rule.evidence) == 1

    def test_extract_rule_from_code_returns_none_on_error_response(self):
        """extract_rule_from_code returns None when LLM returns error."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_llm = Mock()
            mock_response = json.dumps({
                "error": "No rule found",
                "reason": "Code does not contain optimization rule"
            })
            mock_llm.chat = Mock(return_value=mock_response)

            agent = RuleMinerAgent(
                engine="test",
                work_dir=tmpdir,
                category=RuleCategory.RBO,
                source_path="/test",
                llm_client=mock_llm
            )

            code_file = CodeFile(
                path="/test/Utility.java",
                content="public class Utility {}",
                language="java"
            )

            rule = agent.extract_rule_from_code(code_file)
            assert rule is None

    def test_extract_rule_from_code_handles_cbo_category(self):
        """extract_rule_from_code works with CBO category."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_llm = Mock()
            mock_response = json.dumps({
                "rule_id": "C001",
                "rule_name": "JoinOrderOptimization",
                "rule_category": "cbo",
                "implementation_type": "explicitly_implemented",
                "depends_on_stats": True,
                "depends_on_cost": True,
                "confidence": "medium",
                "evidence": []
            })
            mock_llm.chat = Mock(return_value=mock_response)

            agent = RuleMinerAgent(
                engine="starrocks",
                work_dir=tmpdir,
                category=RuleCategory.CBO,
                source_path="/test",
                llm_client=mock_llm
            )

            code_file = CodeFile(
                path="/test/JoinOrderRule.java",
                content="public class JoinOrderRule {}",
                language="java"
            )

            rule = agent.extract_rule_from_code(code_file)

            assert rule is not None
            assert rule.rule_category == RuleCategory.CBO
            assert rule.depends_on_stats is True
            assert rule.depends_on_cost is True

    def test_parse_llm_response_extracts_json(self):
        """_parse_llm_response extracts JSON from response."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = RuleMinerAgent(
                engine="test",
                work_dir=tmpdir,
                category=RuleCategory.RBO,
                source_path="/test"
            )

            # Test with JSON embedded in text
            response = "Here is the result:\n{\"rule_id\": \"R001\"}\nThat's it."
            parsed = agent._parse_llm_response(response)
            assert parsed == {"rule_id": "R001"}

            # Test with pure JSON
            response = '{"rule_id": "R002"}'
            parsed = agent._parse_llm_response(response)
            assert parsed == {"rule_id": "R002"}

            # Test with invalid response
            response = "No JSON here"
            parsed = agent._parse_llm_response(response)
            assert parsed is None

    def test_create_rule_from_data_with_minimal_fields(self):
        """_create_rule_from_data handles minimal data."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = RuleMinerAgent(
                engine="test",
                work_dir=tmpdir,
                category=RuleCategory.RBO,
                source_path="/test"
            )

            code_file = CodeFile(
                path="/test/Rule.java",
                content="public class Rule {}",
                language="java"
            )

            rule_data = {
                "rule_id": "R003",
                "rule_name": "TestRule"
            }

            rule = agent._create_rule_from_data(rule_data, code_file)

            assert rule.rule_id == "R003"
            assert rule.rule_name == "TestRule"
            assert rule.engine == "test"
            assert rule.rule_category == RuleCategory.RBO
            assert len(rule.evidence) == 1
            assert rule.evidence[0].file_path == "/test/Rule.java"

    def test_create_rule_from_data_with_full_fields(self):
        """_create_rule_from_data handles full data."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = RuleMinerAgent(
                engine="postgres",
                work_dir=tmpdir,
                category=RuleCategory.SCALAR,
                source_path="/test"
            )

            code_file = CodeFile(
                path="/test/ScalarRule.java",
                content="public class ScalarRule {}",
                language="java"
            )

            rule_data = {
                "rule_id": "S001",
                "rule_name": "ScalarSubquery",
                "rule_category": "scalar",
                "implementation_type": "explicitly_implemented",
                "lifecycle_stage": "optimization",
                "source_files": ["ScalarRule.java", "Helper.java"],
                "registration_points": ["RuleSet.java"],
                "trigger_pattern": "ScalarSubquery",
                "preconditions": ["isScalar"],
                "transformation_logic": "Rewrite scalar subquery",
                "input_operators": ["Subquery"],
                "output_operators": ["Join"],
                "depends_on_stats": True,
                "depends_on_cost": False,
                "confidence": "high",
                "uncertain_points": ["Line 50 might need review"],
                "evidence": [
                    {
                        "file_path": "/test/ScalarRule.java",
                        "description": "Main rule implementation",
                        "line_start": 10,
                        "line_end": 100,
                        "evidence_type": "source_code"
                    },
                    {
                        "file_path": "/test/RuleTest.java",
                        "description": "Test for this rule",
                        "evidence_type": "test"
                    }
                ]
            }

            rule = agent._create_rule_from_data(rule_data, code_file)

            assert rule.rule_id == "S001"
            assert rule.source_files == ["ScalarRule.java", "Helper.java"]
            assert rule.registration_points == ["RuleSet.java"]
            assert rule.trigger_pattern == "ScalarSubquery"
            assert len(rule.preconditions) == 1
            assert len(rule.evidence) == 2
            assert rule.evidence[1].evidence_type == EvidenceType.TEST

    def test_extract_rule_from_code_llm_called_with_correct_prompts(self):
        """LLM client is called with appropriate prompts."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_llm = Mock()
            mock_llm.chat = Mock(return_value='{"rule_id": "R001"}')

            agent = RuleMinerAgent(
                engine="clickhouse",
                work_dir=tmpdir,
                category=RuleCategory.RBO,
                source_path="/test",
                llm_client=mock_llm
            )

            code_file = CodeFile(
                path="/test/Rule.java",
                content="public class Rule {}",
                language="java"
            )

            agent.extract_rule_from_code(code_file)

            # Verify chat was called with two messages
            assert mock_llm.chat.called
            call_args = mock_llm.chat.call_args
            messages = call_args[0][0]

            assert len(messages) == 2
            assert messages[0].role == "system"
            assert messages[1].role == "user"
            # RBO category should use RBO_RULE_PROMPT
            assert "RBO" in messages[1].content

    def test_extract_rule_from_code_other_categories_use_default_prompt(self):
        """Non-RBO/CBO categories use default user prompt."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_llm = Mock()
            mock_llm.chat = Mock(return_value='{"rule_id": "P001"}')

            agent = RuleMinerAgent(
                engine="test",
                work_dir=tmpdir,
                category=RuleCategory.POST_OPT,
                source_path="/test",
                llm_client=mock_llm
            )

            code_file = CodeFile(
                path="/test/Rule.java",
                content="public class Rule {}",
                language="java"
            )

            agent.extract_rule_from_code(code_file)

            call_args = mock_llm.chat.call_args
            messages = call_args[0][0]

            # Should use default prompt with category placeholder
            assert "post_opt" in messages[1].content


class TestRBOMinerAgent:
    """Tests for RBOMinerAgent specialized miner."""

    def test_rbo_miner_creation(self):
        """RBOMinerAgent can be instantiated correctly."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = RBOMinerAgent(
                engine="clickhouse",
                work_dir=tmpdir,
                source_path="/path/to/rules"
            )
            assert agent.name == "RBOMiner"
            assert agent.engine == "clickhouse"
            assert agent.work_dir == tmpdir
            assert agent.category == RuleCategory.RBO
            assert agent.source_path == "/path/to/rules"
            assert agent.llm_client is None

    def test_rbo_miner_inherits_from_rule_miner(self):
        """RBOMinerAgent inherits from RuleMinerAgent."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = RBOMinerAgent(
                engine="test",
                work_dir=tmpdir,
                source_path="/test"
            )
            assert isinstance(agent, RuleMinerAgent)
            assert isinstance(agent, BaseAgent)

    def test_rbo_miner_with_llm_client(self):
        """RBOMinerAgent can be instantiated with LLM client."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_llm = Mock()
            agent = RBOMinerAgent(
                engine="starrocks",
                work_dir=tmpdir,
                source_path="/path/to/rbo",
                llm_client=mock_llm
            )
            assert agent.llm_client is mock_llm

    def test_rbo_miner_is_rbo_rule_method(self):
        """RBOMinerAgent _is_rbo_rule correctly identifies RBO patterns."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = RBOMinerAgent(
                engine="test",
                work_dir=tmpdir,
                source_path="/test"
            )

            # Test RBO rule patterns
            rbo_content = """
            public class FilterPushdownRule implements Rule {
                // Pattern matching for filter pushdown
                public boolean matches(Operator op) {
                    return op instanceof FilterOperator;
                }
                public Operator transform(Operator input) {
                    // Transform without cost consideration
                    return pushDownFilter(input);
                }
            }
            """
            assert agent._is_rbo_rule({"content": rbo_content, "path": "/rules/FilterPushdownRule.java"}) is True

            # Test CBO-like content (should not match)
            cbo_content = """
            public class CostBasedJoinRule {
                private CostModel costModel;
                public double computeCost(Plan plan) {
                    return costModel.estimateCost(plan);
                }
            }
            """
            assert agent._is_rbo_rule({"content": cbo_content, "path": "/rules/CostBasedJoinRule.java"}) is False

            # Test RBO directory path
            assert agent._is_rbo_rule({"content": "class Rule {}", "path": "/rbo/SomeRule.java"}) is True

    def test_rbo_miner_execute(self):
        """RBOMinerAgent execute method scans and creates artifacts."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a mock source directory with Java files
            source_dir = join(tmpdir, "source")
            makedirs(source_dir, exist_ok=True)

            # Create RBO rule file
            rbo_file = join(source_dir, "FilterRule.java")
            with open(rbo_file, "w") as f:
                f.write("""
                public class FilterRule implements Rule {
                    public boolean matches(Operator op) { return true; }
                    public Operator transform(Operator input) { return input; }
                }
                """)

            agent = RBOMinerAgent(
                engine="clickhouse",
                work_dir=join(tmpdir, "work"),
                source_path=source_dir
            )
            result = agent.execute()

            assert isinstance(result, AgentResult)
            assert result.agent_name == "RBOMiner"
            assert result.status in ["partial", "success"]
            assert "category" in result.metadata
            assert result.metadata["category"] == "rbo"
            assert len(result.artifacts) == 1
            assert exists(result.artifacts[0])
            assert result.artifacts[0].endswith("rbo_rules.json")

            # Verify JSON content
            with open(result.artifacts[0], "r") as f:
                data = json.load(f)
            assert data["engine"] == "clickhouse"
            assert data["category"] == "rbo"


class TestCBOMinerAgent:
    """Tests for CBOMinerAgent specialized miner."""

    def test_cbo_miner_creation(self):
        """CBOMinerAgent can be instantiated correctly."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = CBOMinerAgent(
                engine="starrocks",
                work_dir=tmpdir,
                source_path="/path/to/cbo"
            )
            assert agent.name == "CBOMiner"
            assert agent.engine == "starrocks"
            assert agent.category == RuleCategory.CBO
            assert agent.source_path == "/path/to/cbo"
            assert agent.llm_client is None

    def test_cbo_miner_inherits_from_rule_miner(self):
        """CBOMinerAgent inherits from RuleMinerAgent."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = CBOMinerAgent(
                engine="test",
                work_dir=tmpdir,
                source_path="/test"
            )
            assert isinstance(agent, RuleMinerAgent)

    def test_cbo_miner_with_llm_client(self):
        """CBOMinerAgent can be instantiated with LLM client."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_llm = Mock()
            agent = CBOMinerAgent(
                engine="postgres",
                work_dir=tmpdir,
                source_path="/path/to/cbo",
                llm_client=mock_llm
            )
            assert agent.llm_client is mock_llm

    def test_cbo_miner_is_cbo_rule_method(self):
        """CBOMinerAgent _is_cbo_rule correctly identifies CBO patterns."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = CBOMinerAgent(
                engine="test",
                work_dir=tmpdir,
                source_path="/test"
            )

            # Test CBO rule patterns
            cbo_content = """
            public class JoinOrderRule {
                private CostModel costModel;
                private Statistics stats;
                public Plan chooseBestPlan(List<Plan> plans) {
                    double minCost = Double.MAX_VALUE;
                    for (Plan plan : plans) {
                        double cost = costModel.computeCost(plan, stats);
                        if (cost < minCost) { minCost = cost; }
                    }
                    return bestPlan;
                }
            }
            """
            assert agent._is_cbo_rule({"content": cbo_content, "path": "/rules/JoinOrderRule.java"}) is True

            # Test pure RBO content (should not match)
            rbo_content = """
            public class SimpleTransformRule {
                public Operator transform(Operator op) {
                    return rewritePattern(op);
                }
            }
            """
            assert agent._is_cbo_rule({"content": rbo_content, "path": "/rules/SimpleTransformRule.java"}) is False

            # Test CBO directory path
            assert agent._is_cbo_rule({"content": "class Rule {}", "path": "/cbo/CostRule.java"}) is True

    def test_cbo_miner_execute(self):
        """CBOMinerAgent execute method scans and creates artifacts."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = join(tmpdir, "source")
            makedirs(source_dir, exist_ok=True)

            # Create CBO rule file
            cbo_file = join(source_dir, "CostRule.java")
            with open(cbo_file, "w") as f:
                f.write("""
                public class CostRule {
                    private CostModel costModel;
                    private Statistics statistics;
                    public double estimatedCost(Plan plan) {
                        return costModel.computeCost(plan);
                    }
                }
                """)

            agent = CBOMinerAgent(
                engine="starrocks",
                work_dir=join(tmpdir, "work"),
                source_path=source_dir
            )
            result = agent.execute()

            assert isinstance(result, AgentResult)
            assert result.agent_name == "CBOMiner"
            assert result.status in ["partial", "success"]
            assert result.metadata["category"] == "cbo"
            assert len(result.artifacts) == 1
            assert exists(result.artifacts[0])
            assert result.artifacts[0].endswith("cbo_rules.json")

            with open(result.artifacts[0], "r") as f:
                data = json.load(f)
            assert data["engine"] == "starrocks"
            assert data["category"] == "cbo"


class TestScalarRuleMinerAgent:
    """Tests for ScalarRuleMinerAgent specialized miner."""

    def test_scalar_miner_creation(self):
        """ScalarRuleMinerAgent can be instantiated correctly."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = ScalarRuleMinerAgent(
                engine="clickhouse",
                work_dir=tmpdir,
                source_path="/path/to/scalar"
            )
            assert agent.name == "ScalarRuleMiner"
            assert agent.engine == "clickhouse"
            assert agent.category == RuleCategory.SCALAR
            assert agent.source_path == "/path/to/scalar"
            assert agent.llm_client is None

    def test_scalar_miner_inherits_from_rule_miner(self):
        """ScalarRuleMinerAgent inherits from RuleMinerAgent."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = ScalarRuleMinerAgent(
                engine="test",
                work_dir=tmpdir,
                source_path="/test"
            )
            assert isinstance(agent, RuleMinerAgent)

    def test_scalar_miner_with_llm_client(self):
        """ScalarRuleMinerAgent can be instantiated with LLM client."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_llm = Mock()
            agent = ScalarRuleMinerAgent(
                engine="postgres",
                work_dir=tmpdir,
                source_path="/path/to/scalar",
                llm_client=mock_llm
            )
            assert agent.llm_client is mock_llm

    def test_scalar_miner_is_scalar_rule_method(self):
        """ScalarRuleMinerAgent _is_scalar_rule correctly identifies scalar patterns."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = ScalarRuleMinerAgent(
                engine="test",
                work_dir=tmpdir,
                source_path="/test"
            )

            # Test scalar rule patterns
            scalar_content = """
            public class ConstantFoldingRule {
                public Expression foldConstants(Expression expr) {
                    if (expr.isConstant()) {
                        return evaluateLiteral(expr);
                    }
                    return expr;
                }
            }
            """
            assert agent._is_scalar_rule({"content": scalar_content, "path": "/rules/ConstantFoldingRule.java"}) is True

            # Test scalar directory path
            assert agent._is_scalar_rule({"content": "class Rule {}", "path": "/scalar/SubqueryRule.java"}) is True

            # Test non-scalar content
            nonscalar_content = """
            public class JoinRule {
                public Plan optimizeJoin(Plan plan) { return plan; }
            }
            """
            assert agent._is_scalar_rule({"content": nonscalar_content, "path": "/rules/JoinRule.java"}) is False

    def test_scalar_miner_execute(self):
        """ScalarRuleMinerAgent execute method scans and creates artifacts."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = join(tmpdir, "source")
            makedirs(source_dir, exist_ok=True)

            # Create scalar rule file
            scalar_file = join(source_dir, "ScalarRule.java")
            with open(scalar_file, "w") as f:
                f.write("""
                public class ScalarRule {
                    public Expression simplifyScalar(Expression expr) {
                        if (expr.isScalarSubquery()) {
                            return evaluateSubquery(expr);
                        }
                        return foldConstants(expr);
                    }
                }
                """)

            agent = ScalarRuleMinerAgent(
                engine="clickhouse",
                work_dir=join(tmpdir, "work"),
                source_path=source_dir
            )
            result = agent.execute()

            assert isinstance(result, AgentResult)
            assert result.agent_name == "ScalarRuleMiner"
            assert result.status in ["partial", "success"]
            assert result.metadata["category"] == "scalar"
            assert len(result.artifacts) == 1
            assert exists(result.artifacts[0])
            assert result.artifacts[0].endswith("scalar_rules.json")

            with open(result.artifacts[0], "r") as f:
                data = json.load(f)
            assert data["engine"] == "clickhouse"
            assert data["category"] == "scalar"


class TestPostOptimizerMinerAgent:
    """Tests for PostOptimizerMinerAgent specialized miner."""

    def test_post_optimizer_miner_creation(self):
        """PostOptimizerMinerAgent can be instantiated correctly."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = PostOptimizerMinerAgent(
                engine="starrocks",
                work_dir=tmpdir,
                source_path="/path/to/post_opt"
            )
            assert agent.name == "PostOptimizerMiner"
            assert agent.engine == "starrocks"
            assert agent.category == RuleCategory.POST_OPT
            assert agent.source_path == "/path/to/post_opt"
            assert agent.llm_client is None

    def test_post_optimizer_miner_inherits_from_rule_miner(self):
        """PostOptimizerMinerAgent inherits from RuleMinerAgent."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = PostOptimizerMinerAgent(
                engine="test",
                work_dir=tmpdir,
                source_path="/test"
            )
            assert isinstance(agent, RuleMinerAgent)

    def test_post_optimizer_miner_with_llm_client(self):
        """PostOptimizerMinerAgent can be instantiated with LLM client."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_llm = Mock()
            agent = PostOptimizerMinerAgent(
                engine="clickhouse",
                work_dir=tmpdir,
                source_path="/path/to/post_opt",
                llm_client=mock_llm
            )
            assert agent.llm_client is mock_llm

    def test_post_optimizer_miner_is_post_opt_rule_method(self):
        """PostOptimizerMinerAgent _is_post_opt_rule correctly identifies post-opt patterns."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = PostOptimizerMinerAgent(
                engine="test",
                work_dir=tmpdir,
                source_path="/test"
            )

            # Test post-opt rule patterns
            post_opt_content = """
            public class PlanRefinementRule {
                public void postOptimize(Plan plan) {
                    refinePlan(plan);
                    finalizePlanProperties(plan);
                }
            }
            """
            assert agent._is_post_opt_rule({"content": post_opt_content, "path": "/rules/PlanRefinementRule.java"}) is True

            # Test post-opt directory path
            assert agent._is_post_opt_rule({"content": "class Rule {}", "path": "/postopt/FinalRule.java"}) is True

            # Test non-post-opt content
            normal_content = """
            public class NormalRule {
                public Plan optimize(Plan plan) { return plan; }
            }
            """
            assert agent._is_post_opt_rule({"content": normal_content, "path": "/rules/NormalRule.java"}) is False

    def test_post_optimizer_miner_execute(self):
        """PostOptimizerMinerAgent execute method scans and creates artifacts."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = join(tmpdir, "source")
            makedirs(source_dir, exist_ok=True)

            # Create post-opt rule file
            post_opt_file = join(source_dir, "PostOptRule.java")
            with open(post_opt_file, "w") as f:
                f.write("""
                public class PostOptRule {
                    public void post_optimize(Plan plan) {
                        refinePlan(plan);
                    }
                }
                """)

            agent = PostOptimizerMinerAgent(
                engine="starrocks",
                work_dir=join(tmpdir, "work"),
                source_path=source_dir
            )
            result = agent.execute()

            assert isinstance(result, AgentResult)
            assert result.agent_name == "PostOptimizerMiner"
            assert result.status in ["partial", "success"]
            assert result.metadata["category"] == "post_opt"
            assert len(result.artifacts) == 1
            assert exists(result.artifacts[0])
            assert result.artifacts[0].endswith("post_opt_rules.json")

            with open(result.artifacts[0], "r") as f:
                data = json.load(f)
            assert data["engine"] == "starrocks"
            assert data["category"] == "post_opt"


class TestSpecializedMinersExports:
    """Tests for specialized miner exports from agents module."""

    def test_specialized_miners_exported_from_agents_module(self):
        """All specialized miners are exported from agents.__init__."""
        from optimizer_analysis.agents import (
            CBOMinerAgent,
            PostOptimizerMinerAgent,
            RBOMinerAgent,
            ScalarRuleMinerAgent,
        )

        # Verify they are the correct classes
        assert CBOMinerAgent.name == "CBOMiner"
        assert RBOMinerAgent.name == "RBOMiner"
        assert ScalarRuleMinerAgent.name == "ScalarRuleMiner"
        assert PostOptimizerMinerAgent.name == "PostOptimizerMiner"

    def test_specialized_miners_in_all_list(self):
        """Specialized miners are in __all__ list."""
        import optimizer_analysis.agents as agents_module

        assert "RBOMinerAgent" in agents_module.__all__
        assert "CBOMinerAgent" in agents_module.__all__
        assert "ScalarRuleMinerAgent" in agents_module.__all__
        assert "PostOptimizerMinerAgent" in agents_module.__all__