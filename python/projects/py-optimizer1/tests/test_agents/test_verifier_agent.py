"""Tests for Verifier Agent and verification models."""

import json
from os.path import exists, join
from typing import List

from optimizer_analysis.agents.base import AgentResult
from optimizer_analysis.agents.lifecycle import LifecycleInfo, PhaseInfo
from optimizer_analysis.agents.verifier_agent import (
    VerificationIssue,
    VerificationResult,
    VerifierAgent,
)
from optimizer_analysis.schemas.base import Evidence, EvidenceType
from optimizer_analysis.schemas.framework import Framework, EngineType, OptimizerStyle
from optimizer_analysis.schemas.rule import Rule, RuleCategory, ImplementationType


class TestVerificationIssue:
    """Tests for VerificationIssue model."""

    def test_verification_issue_creation(self):
        """VerificationIssue basic creation with required fields."""
        issue = VerificationIssue(
            severity="error",
            category="evidence",
            message="Missing evidence for rule",
            engine="starrocks"
        )
        assert issue.severity == "error"
        assert issue.category == "evidence"
        assert issue.message == "Missing evidence for rule"
        assert issue.engine == "starrocks"
        assert issue.file_path is None
        assert issue.line_number is None
        assert issue.suggestion is None

    def test_verification_issue_with_optional_fields(self):
        """VerificationIssue with optional fields populated."""
        issue = VerificationIssue(
            severity="warning",
            category="lifecycle",
            message="Phase has no transitions",
            engine="clickhouse",
            file_path="optimizer/phase.cpp",
            line_number=42,
            suggestion="Add transition targets for this phase"
        )
        assert issue.severity == "warning"
        assert issue.category == "lifecycle"
        assert issue.file_path == "optimizer/phase.cpp"
        assert issue.line_number == 42
        assert issue.suggestion == "Add transition targets for this phase"

    def test_verification_issue_severity_values(self):
        """VerificationIssue supports error, warning, info severity."""
        severities = ["error", "warning", "info"]
        for sev in severities:
            issue = VerificationIssue(
                severity=sev,
                category="test",
                message=f"Test {sev} issue",
                engine="test"
            )
            assert issue.severity == sev

    def test_verification_issue_json_serialization(self):
        """VerificationIssue can be serialized to JSON."""
        issue = VerificationIssue(
            severity="error",
            category="rule",
            message="Empty source_files",
            engine="postgres",
            file_path="rule_123",
            suggestion="Add source files"
        )
        json_str = issue.model_dump_json()
        data = json.loads(json_str)
        assert data["severity"] == "error"
        assert data["category"] == "rule"
        assert data["message"] == "Empty source_files"
        assert data["file_path"] == "rule_123"


class TestVerificationResult:
    """Tests for VerificationResult model."""

    def test_verification_result_creation(self):
        """VerificationResult basic creation."""
        result = VerificationResult(
            engine="starrocks",
            passed=True,
            issues=[],
            checked_items=5,
            warnings=0,
            errors=0
        )
        assert result.engine == "starrocks"
        assert result.passed is True
        assert result.issues == []
        assert result.checked_items == 5
        assert result.warnings == 0
        assert result.errors == 0

    def test_verification_result_with_issues(self):
        """VerificationResult with issues."""
        issues = [
            VerificationIssue(
                severity="warning",
                category="lifecycle",
                message="Gap in phase sequence",
                engine="test"
            ),
            VerificationIssue(
                severity="error",
                category="evidence",
                message="No evidence found",
                engine="test"
            )
        ]
        result = VerificationResult(
            engine="test",
            passed=False,
            issues=issues,
            checked_items=3,
            warnings=1,
            errors=1
        )
        assert result.passed is False
        assert len(result.issues) == 2
        assert result.warnings == 1
        assert result.errors == 1

    def test_verification_result_json_serialization(self):
        """VerificationResult can be serialized to JSON."""
        result = VerificationResult(
            engine="clickhouse",
            passed=True,
            issues=[
                VerificationIssue(
                    severity="info",
                    category="rule",
                    message="Low confidence",
                    engine="clickhouse"
                )
            ],
            checked_items=10,
            warnings=0,
            errors=0
        )
        json_str = result.model_dump_json()
        data = json.loads(json_str)
        assert data["engine"] == "clickhouse"
        assert data["passed"] is True
        assert len(data["issues"]) == 1
        assert data["checked_items"] == 10


class TestVerifierAgent:
    """Tests for VerifierAgent class."""

    def test_verifier_agent_creation(self):
        """VerifierAgent can be instantiated correctly."""
        agent = VerifierAgent(
            engine="starrocks",
            work_dir="/tmp/work",
            analysis_result={}
        )
        assert agent.name == "VerifierAgent"
        assert agent.engine == "starrocks"
        assert agent.work_dir == "/tmp/work"
        assert agent.analysis_result == {}
        assert agent.llm_client is None

    def test_verifier_agent_with_llm_client(self):
        """VerifierAgent can be instantiated with LLM client."""
        # Mock LLM client
        class MockLLMClient:
            pass

        agent = VerifierAgent(
            engine="clickhouse",
            work_dir="/tmp/work",
            analysis_result={},
            llm_client=MockLLMClient()
        )
        assert agent.llm_client is not None

    def test_verifier_agent_inherits_from_base_agent(self):
        """VerifierAgent inherits from BaseAgent."""
        from optimizer_analysis.agents.base import BaseAgent

        agent = VerifierAgent(
            engine="test",
            work_dir="/tmp",
            analysis_result={}
        )
        assert isinstance(agent, BaseAgent)

    def test_verifier_agent_execute(self):
        """VerifierAgent execute returns AgentResult."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = VerifierAgent(
                engine="test_engine",
                work_dir=join(tmpdir, "work"),
                analysis_result={}
            )
            result = agent.execute()

            assert isinstance(result, AgentResult)
            assert result.agent_name == "VerifierAgent"
            assert result.status == "success"
            assert len(result.artifacts) == 1
            assert result.artifacts[0].endswith("verification_result.json")

    def test_verifier_agent_creates_verification_directory(self):
        """VerifierAgent creates verification subdirectory."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = join(tmpdir, "work")
            agent = VerifierAgent(
                engine="postgres",
                work_dir=work_dir,
                analysis_result={}
            )
            result = agent.execute()

            # Check verification directory was created
            verification_dir = join(work_dir, "verification")
            assert exists(verification_dir)
            assert exists(join(verification_dir, "verification_result.json"))


class TestVerifyEvidence:
    """Tests for verify_evidence method."""

    def test_verify_evidence_no_issues(self):
        """verify_evidence returns no issues for rule with proper evidence."""
        agent = VerifierAgent(
            engine="test",
            work_dir="/tmp",
            analysis_result={}
        )

        rule = Rule(
            rule_id="RULE_001",
            rule_name="FilterPushDown",
            engine="test",
            rule_category=RuleCategory.RBO,
            evidence=[
                Evidence(
                    file_path="src/FilterRule.cpp",
                    description="Filter push-down rule implementation"
                )
            ]
        )

        issues = agent.verify_evidence(rule)
        assert len(issues) == 0

    def test_verify_evidence_missing_evidence(self):
        """verify_evidence detects missing evidence."""
        agent = VerifierAgent(
            engine="test",
            work_dir="/tmp",
            analysis_result={}
        )

        rule = Rule(
            rule_id="RULE_002",
            rule_name="JoinRule",
            engine="test",
            rule_category=RuleCategory.CBO,
            evidence=[]
        )

        issues = agent.verify_evidence(rule)
        assert len(issues) == 1
        assert issues[0].severity == "error"
        assert issues[0].category == "evidence"
        assert "no evidence" in issues[0].message.lower()

    def test_verify_evidence_missing_file_path(self):
        """verify_evidence detects evidence without file_path."""
        agent = VerifierAgent(
            engine="test",
            work_dir="/tmp",
            analysis_result={}
        )

        rule = Rule(
            rule_id="RULE_003",
            rule_name="TestRule",
            engine="test",
            rule_category=RuleCategory.RBO,
            evidence=[
                Evidence(
                    file_path="",  # Empty file_path
                    description="Some description"
                )
            ]
        )

        issues = agent.verify_evidence(rule)
        assert len(issues) >= 1
        # Should have warning about missing file_path
        file_path_issues = [i for i in issues if "file_path" in i.message.lower()]
        assert len(file_path_issues) >= 1

    def test_verify_evidence_framework(self):
        """verify_evidence works with Framework objects."""
        agent = VerifierAgent(
            engine="test",
            work_dir="/tmp",
            analysis_result={}
        )

        framework = Framework(
            engine_name="test",
            engine_type=EngineType.COLUMNAR_OLAP,
            optimizer_style=OptimizerStyle.CASCADES,
            main_entry="src/optimizer.cpp",
            evidence=[
                Evidence(
                    file_path="src/optimizer.cpp",
                    description="Main optimizer entry point"
                )
            ]
        )

        issues = agent.verify_evidence(framework)
        assert len(issues) == 0


class TestVerifyLifecycle:
    """Tests for verify_lifecycle method."""

    def test_verify_lifecycle_no_issues(self):
        """verify_lifecycle returns no issues for proper lifecycle."""
        agent = VerifierAgent(
            engine="test",
            work_dir="/tmp",
            analysis_result={}
        )

        lifecycle = LifecycleInfo(
            engine="test",
            phases=[
                PhaseInfo(phase="Parsing", transitions_to=["Analysis"]),
                PhaseInfo(phase="Analysis", transitions_to=["Planning"]),
                PhaseInfo(phase="Planning", transitions_to=["Execution"]),
                PhaseInfo(phase="Execution", transitions_to=[])
            ],
            phase_sequence=["Parsing", "Analysis", "Planning", "Execution"],
            confidence="high"
        )

        issues = agent.verify_lifecycle(lifecycle)
        # Should have no error-level issues
        error_issues = [i for i in issues if i.severity == "error"]
        assert len(error_issues) == 0

    def test_verify_lifecycle_missing_phases(self):
        """verify_lifecycle detects missing phases."""
        agent = VerifierAgent(
            engine="test",
            work_dir="/tmp",
            analysis_result={}
        )

        lifecycle = LifecycleInfo(
            engine="test",
            phases=[],
            phase_sequence=["Parsing", "Analysis"]
        )

        issues = agent.verify_lifecycle(lifecycle)
        assert len(issues) >= 1
        assert issues[0].severity == "error"
        assert "no phases" in issues[0].message.lower()

    def test_verify_lifecycle_disconnected_phase(self):
        """verify_lifecycle detects phases without transitions."""
        agent = VerifierAgent(
            engine="test",
            work_dir="/tmp",
            analysis_result={}
        )

        lifecycle = LifecycleInfo(
            engine="test",
            phases=[
                PhaseInfo(phase="Parsing", transitions_to=["Analysis"]),
                PhaseInfo(phase="Planning", transitions_to=[]),  # Disconnected, not final
            ],
            phase_sequence=["Parsing", "Analysis", "Planning", "Execution"]
        )

        issues = agent.verify_lifecycle(lifecycle)
        # Should have warning about Planning not being the final phase
        transition_issues = [i for i in issues if "no transitions" in i.message.lower()]
        assert len(transition_issues) >= 1

    def test_verify_lifecycle_unknown_confidence(self):
        """verify_lifecycle warns about unknown confidence."""
        agent = VerifierAgent(
            engine="test",
            work_dir="/tmp",
            analysis_result={}
        )

        lifecycle = LifecycleInfo(
            engine="test",
            phases=[
                PhaseInfo(phase="Parsing", transitions_to=["Analysis"]),
            ],
            phase_sequence=["Parsing", "Analysis"],
            confidence="unknown"
        )

        issues = agent.verify_lifecycle(lifecycle)
        confidence_issues = [i for i in issues if "confidence" in i.message.lower()]
        assert len(confidence_issues) >= 1


class TestVerifyRules:
    """Tests for verify_rules method."""

    def test_verify_rules_empty_source_files(self):
        """verify_rules detects empty source_files."""
        agent = VerifierAgent(
            engine="test",
            work_dir="/tmp",
            analysis_result={}
        )

        rules = [
            Rule(
                rule_id="RULE_001",
                rule_name="TestRule",
                engine="test",
                rule_category=RuleCategory.RBO,
                source_files=[]  # Empty
            )
        ]

        issues = agent.verify_rules(rules)
        source_issues = [i for i in issues if "source_files" in i.message.lower()]
        assert len(source_issues) >= 1
        assert source_issues[0].severity == "error"

    def test_verify_rules_missing_rule_id(self):
        """verify_rules detects missing rule_id."""
        agent = VerifierAgent(
            engine="test",
            work_dir="/tmp",
            analysis_result={}
        )

        rules = [
            Rule(
                rule_id="UNKNOWN",
                rule_name="TestRule",
                engine="test",
                rule_category=RuleCategory.RBO,
                source_files=["src/test.cpp"]
            )
        ]

        issues = agent.verify_rules(rules)
        id_issues = [i for i in issues if "rule_id" in i.message.lower()]
        assert len(id_issues) >= 1

    def test_verify_rules_low_confidence_no_uncertain_points(self):
        """verify_rules detects low confidence without uncertain_points."""
        agent = VerifierAgent(
            engine="test",
            work_dir="/tmp",
            analysis_result={}
        )

        rules = [
            Rule(
                rule_id="RULE_001",
                rule_name="UncertainRule",
                engine="test",
                rule_category=RuleCategory.CBO,
                source_files=["src/uncertain.cpp"],
                confidence="low",
                uncertain_points=[]  # Empty
            )
        ]

        issues = agent.verify_rules(rules)
        confidence_issues = [i for i in issues if "confidence" in i.message.lower() and "uncertain" in i.message.lower()]
        assert len(confidence_issues) >= 1


class TestUnsupportedClaims:
    """Tests for check_unsupported_claims method."""

    def test_check_unsupported_claims_unknown_confidence(self):
        """check_unsupported_claims detects unknown confidence without explanation."""
        agent = VerifierAgent(
            engine="test",
            work_dir="/tmp",
            analysis_result={
                "rules": [
                    Rule(
                        rule_id="RULE_001",
                        rule_name="UnknownRule",
                        engine="test",
                        rule_category=RuleCategory.RBO,
                        source_files=["src/unknown.cpp"],
                        confidence="unknown",
                        uncertain_points=[]
                    )
                ]
            }
        )

        issues = agent.check_unsupported_claims()
        assert len(issues) >= 1
        unsupported_issues = [i for i in issues if i.category == "unsupported_claims"]
        assert len(unsupported_issues) >= 1


class TestVerifyAll:
    """Tests for verify_all method."""

    def test_verify_all_combines_results(self):
        """verify_all runs all checks and combines results."""
        agent = VerifierAgent(
            engine="test",
            work_dir="/tmp",
            analysis_result={
                "rules": [
                    Rule(
                        rule_id="RULE_001",
                        rule_name="GoodRule",
                        engine="test",
                        rule_category=RuleCategory.RBO,
                        source_files=["src/good.cpp"],
                        evidence=[
                            Evidence(
                                file_path="src/good.cpp",
                                description="Good rule implementation"
                            )
                        ],
                        confidence="high"
                    )
                ],
                "lifecycle": LifecycleInfo(
                    engine="test",
                    phases=[
                        PhaseInfo(phase="Parse", transitions_to=["Plan"]),
                        PhaseInfo(phase="Plan", transitions_to=["Execute"]),
                        PhaseInfo(phase="Execute", transitions_to=[])
                    ],
                    phase_sequence=["Parse", "Plan", "Execute"],
                    confidence="high"
                )
            }
        )

        result = agent.verify_all()
        assert isinstance(result, VerificationResult)
        assert result.engine == "test"
        assert result.checked_items == 2  # 1 rule + 1 lifecycle
        # Should pass since everything is valid
        error_count = sum(1 for i in result.issues if i.severity == "error")
        assert error_count == 0

    def test_verify_all_with_issues(self):
        """verify_all aggregates all issues."""
        agent = VerifierAgent(
            engine="test",
            work_dir="/tmp",
            analysis_result={
                "rules": [
                    Rule(
                        rule_id="RULE_001",
                        rule_name="BadRule",
                        engine="test",
                        rule_category=RuleCategory.RBO,
                        source_files=[],  # Empty - will cause error
                        evidence=[]  # Empty - will cause error
                    )
                ]
            }
        )

        result = agent.verify_all()
        assert len(result.issues) >= 2
        assert result.passed is False