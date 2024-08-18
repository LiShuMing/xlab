"""Verifier Agent for validating analysis results and checking data quality."""

from os import makedirs
from os.path import exists, join
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from optimizer_analysis.agents.base import AgentResult, BaseAgent
from optimizer_analysis.agents.lifecycle import LifecycleInfo
from optimizer_analysis.schemas.framework import Framework
from optimizer_analysis.schemas.rule import Rule


class VerificationIssue(BaseModel):
    """A single issue found during verification.

    This model captures issues detected during the verification process,
    including severity, category, and suggestions for resolution.
    """

    severity: str = Field(
        ...,
        description="Issue severity: 'error', 'warning', or 'info'"
    )
    category: str = Field(
        ...,
        description="Category of the issue (e.g., 'evidence', 'lifecycle', 'rule')"
    )
    message: str = Field(
        ...,
        description="Description of the issue"
    )
    engine: str = Field(
        ...,
        description="Engine this issue relates to"
    )
    file_path: Optional[str] = Field(
        None,
        description="File path related to this issue, if applicable"
    )
    line_number: Optional[int] = Field(
        None,
        description="Line number related to this issue, if applicable"
    )
    suggestion: Optional[str] = Field(
        None,
        description="Suggested resolution for this issue"
    )


class VerificationResult(BaseModel):
    """Result of running verification checks on analysis data.

    This model captures the overall verification outcome, including
    all issues found and summary statistics.
    """

    engine: str = Field(
        ...,
        description="Engine that was verified"
    )
    passed: bool = Field(
        ...,
        description="Whether verification passed (no errors)"
    )
    issues: List[VerificationIssue] = Field(
        default_factory=list,
        description="List of all issues found during verification"
    )
    checked_items: int = Field(
        0,
        description="Total number of items checked"
    )
    warnings: int = Field(
        0,
        description="Number of warning-level issues"
    )
    errors: int = Field(
        0,
        description="Number of error-level issues"
    )


class VerifierAgent(BaseAgent):
    """Agent for verifying analysis results and checking data quality.

    This agent performs verification checks on analysis results to ensure
    data quality, completeness, and consistency. It checks for missing
    evidence, lifecycle gaps, empty source files, and unsupported claims.
    """

    name = "VerifierAgent"

    def __init__(
        self,
        engine: str,
        work_dir: str,
        analysis_result: Dict[str, Any],
        llm_client: Optional[object] = None
    ):
        """Initialize the verifier agent.

        Args:
            engine: The optimizer engine name.
            work_dir: Working directory for storing artifacts.
            analysis_result: Dictionary containing analysis results to verify.
                Expected keys: 'rules', 'framework', 'lifecycle'.
            llm_client: Optional LLM client for enhanced verification.
        """
        super().__init__(engine, work_dir)
        self.analysis_result = analysis_result
        self.llm_client = llm_client

    def execute(self) -> AgentResult:
        """Execute the verification task.

        Runs all verification checks and produces a VerificationResult.

        Returns:
            AgentResult containing the VerificationResult and execution status.
        """
        errors: List[str] = []
        artifacts: List[str] = []

        try:
            # Ensure work directory exists
            if not exists(self.work_dir):
                makedirs(self.work_dir, exist_ok=True)

            # Create verification subdirectory
            verification_dir = join(self.work_dir, "verification")
            if not exists(verification_dir):
                makedirs(verification_dir, exist_ok=True)

            # Run all verification checks
            all_issues: List[VerificationIssue] = []
            checked_items = 0

            # Verify rules
            rules = self.analysis_result.get("rules", [])
            if rules:
                rule_issues = self.verify_rules(rules)
                all_issues.extend(rule_issues)
                checked_items += len(rules)

            # Verify framework
            framework = self.analysis_result.get("framework")
            if framework:
                framework_issues = self.verify_evidence(framework)
                all_issues.extend(framework_issues)
                checked_items += 1

            # Verify lifecycle
            lifecycle = self.analysis_result.get("lifecycle")
            if lifecycle:
                lifecycle_issues = self.verify_lifecycle(lifecycle)
                all_issues.extend(lifecycle_issues)
                checked_items += 1

            # Check for unsupported claims
            unsupported_issues = self.check_unsupported_claims()
            all_issues.extend(unsupported_issues)

            # Calculate statistics
            error_count = sum(1 for i in all_issues if i.severity == "error")
            warning_count = sum(1 for i in all_issues if i.severity == "warning")

            # Create verification result
            verification_result = VerificationResult(
                engine=self.engine,
                passed=error_count == 0,
                issues=all_issues,
                checked_items=checked_items,
                warnings=warning_count,
                errors=error_count
            )

            # Save the verification result as JSON artifact
            verification_json_path = join(verification_dir, "verification_result.json")
            with open(verification_json_path, "w") as f:
                f.write(verification_result.model_dump_json(indent=2))
            artifacts.append(verification_json_path)

            # Determine status based on issues
            status = "success" if error_count == 0 else "partial" if error_count < 3 else "failed"

            return AgentResult(
                agent_name=self.name,
                status=status,
                artifacts=artifacts,
                errors=errors,
                summary=(
                    f"Verification completed for {self.engine}. "
                    f"Checked {checked_items} items, found {error_count} errors, "
                    f"{warning_count} warnings. "
                    f"Verification result saved to {verification_json_path}"
                ),
                metadata={
                    "passed": verification_result.passed,
                    "errors": error_count,
                    "warnings": warning_count,
                    "checked_items": checked_items,
                    "has_llm_client": self.llm_client is not None
                }
            )

        except Exception as e:
            errors.append(f"Verification failed: {str(e)}")
            return AgentResult(
                agent_name=self.name,
                status="failed",
                artifacts=artifacts,
                errors=errors,
                summary=f"Verification failed for {self.engine}",
                metadata={"error": str(e)}
            )

    def verify_evidence(self, rule: Any) -> List[VerificationIssue]:
        """Verify that a Rule or Framework has proper evidence.

        Checks that claims are supported by evidence from source code,
        documentation, or other sources.

        Args:
            rule: A Rule or Framework object to verify.

        Returns:
            List of VerificationIssue objects found.
        """
        issues: List[VerificationIssue] = []

        # Get the evidence list
        evidence_list = getattr(rule, "evidence", [])

        # Check if evidence exists
        if not evidence_list:
            # Determine what type of object we're checking
            obj_type = "Framework" if hasattr(rule, "engine_type") else "Rule"
            obj_name = getattr(rule, "rule_name", getattr(rule, "engine_name", "unknown"))

            issues.append(VerificationIssue(
                severity="error",
                category="evidence",
                message=f"{obj_type} '{obj_name}' has no evidence supporting its analysis",
                engine=self.engine,
                suggestion="Add Evidence objects with source code references or documentation links"
            ))

        # Check if evidence has required fields
        for idx, evidence in enumerate(evidence_list):
            if not hasattr(evidence, "file_path") or not evidence.file_path:
                issues.append(VerificationIssue(
                    severity="warning",
                    category="evidence",
                    message=f"Evidence #{idx + 1} missing file_path field",
                    engine=self.engine,
                    suggestion="Specify the source file path for this evidence"
                ))

            if not hasattr(evidence, "description") or not evidence.description:
                issues.append(VerificationIssue(
                    severity="warning",
                    category="evidence",
                    message=f"Evidence #{idx + 1} missing description field",
                    engine=self.engine,
                    suggestion="Add a description explaining what this evidence demonstrates"
                ))

        return issues

    def verify_lifecycle(self, lifecycle: LifecycleInfo) -> List[VerificationIssue]:
        """Verify lifecycle information for consistency and completeness.

        Checks that phases are connected properly without gaps and that
        the phase sequence is logical.

        Args:
            lifecycle: LifecycleInfo object to verify.

        Returns:
            List of VerificationIssue objects found.
        """
        issues: List[VerificationIssue] = []

        # Check if phases exist
        if not lifecycle.phases:
            issues.append(VerificationIssue(
                severity="error",
                category="lifecycle",
                message="Lifecycle has no phases defined",
                engine=self.engine,
                suggestion="Add PhaseInfo objects describing the optimizer phases"
            ))
            return issues

        # Check phase sequence consistency
        phase_sequence = lifecycle.phase_sequence
        phase_names = [p.phase for p in lifecycle.phases]

        # Verify all phases in sequence have PhaseInfo
        for seq_phase in phase_sequence:
            if seq_phase not in phase_names:
                issues.append(VerificationIssue(
                    severity="warning",
                    category="lifecycle",
                    message=f"Phase '{seq_phase}' in sequence but missing PhaseInfo",
                    engine=self.engine,
                    suggestion=f"Add PhaseInfo for phase '{seq_phase}'"
                ))

        # Check for disconnected phases (phases with no transitions)
        for phase in lifecycle.phases:
            if not phase.transitions_to and phase.phase != phase_sequence[-1]:
                # Only final phase should have no transitions
                issues.append(VerificationIssue(
                    severity="warning",
                    category="lifecycle",
                    message=f"Phase '{phase.phase}' has no transitions_to defined",
                    engine=self.engine,
                    suggestion=f"Add transition targets for phase '{phase.phase}'"
                ))

        # Check for gaps in phase transitions
        all_transition_targets = set()
        for phase in lifecycle.phases:
            all_transition_targets.update(phase.transitions_to)

        # Check if all transition targets have corresponding PhaseInfo
        for target in all_transition_targets:
            if target not in phase_names and target not in phase_sequence:
                issues.append(VerificationIssue(
                    severity="warning",
                    category="lifecycle",
                    message=f"Transition target '{target}' not defined as a phase",
                    engine=self.engine,
                    suggestion=f"Add PhaseInfo for phase '{target}' or fix the transition"
                ))

        # Check confidence level
        if lifecycle.confidence == "unknown":
            issues.append(VerificationIssue(
                severity="info",
                category="lifecycle",
                message="Lifecycle confidence is 'unknown'",
                engine=self.engine,
                suggestion="Review lifecycle analysis and set appropriate confidence level"
            ))

        return issues

    def verify_rules(self, rules: List[Rule]) -> List[VerificationIssue]:
        """Verify rules for completeness and proper structure.

        Checks that rules have source_files, proper evidence, and
        other required fields.

        Args:
            rules: List of Rule objects to verify.

        Returns:
            List of VerificationIssue objects found.
        """
        issues: List[VerificationIssue] = []

        for idx, rule in enumerate(rules):
            # Check for empty source_files
            if not rule.source_files:
                issues.append(VerificationIssue(
                    severity="error",
                    category="rule",
                    message=f"Rule '{rule.rule_name}' (index {idx}) has empty source_files",
                    engine=self.engine,
                    file_path=rule.rule_id,
                    suggestion="Add source file paths where this rule is implemented"
                ))

            # Check for missing rule_id
            if not rule.rule_id or rule.rule_id == "UNKNOWN":
                issues.append(VerificationIssue(
                    severity="warning",
                    category="rule",
                    message=f"Rule '{rule.rule_name}' has missing or placeholder rule_id",
                    engine=self.engine,
                    suggestion="Assign a unique rule identifier"
                ))

            # Verify evidence for this rule
            evidence_issues = self.verify_evidence(rule)
            issues.extend(evidence_issues)

            # Check for low confidence without explanation
            if rule.confidence == "low" and not rule.uncertain_points:
                issues.append(VerificationIssue(
                    severity="warning",
                    category="rule",
                    message=f"Rule '{rule.rule_name}' has low confidence but no uncertain_points",
                    engine=self.engine,
                    file_path=rule.rule_id,
                    suggestion="Add uncertain_points explaining the low confidence areas"
                ))

        return issues

    def check_unsupported_claims(self) -> List[VerificationIssue]:
        """Check for unsupported claims across all analysis data.

        Identifies items with confidence='unknown' without proper explanation
        or evidence.

        Returns:
            List of VerificationIssue objects found.
        """
        issues: List[VerificationIssue] = []

        # Check rules for unsupported claims
        rules = self.analysis_result.get("rules", [])
        for rule in rules:
            confidence = getattr(rule, "confidence", "medium")
            uncertain_points = getattr(rule, "uncertain_points", [])
            evidence = getattr(rule, "evidence", [])

            if confidence == "unknown":
                if not uncertain_points:
                    rule_name = getattr(rule, "rule_name", "unknown")
                    issues.append(VerificationIssue(
                        severity="error",
                        category="unsupported_claims",
                        message=f"Rule '{rule_name}' has 'unknown' confidence without explanation",
                        engine=self.engine,
                        file_path=getattr(rule, "rule_id", None),
                        suggestion="Add uncertain_points explaining why confidence is unknown"
                    ))

                if not evidence:
                    rule_name = getattr(rule, "rule_name", "unknown")
                    issues.append(VerificationIssue(
                        severity="error",
                        category="unsupported_claims",
                        message=f"Rule '{rule_name}' has 'unknown' confidence and no evidence",
                        engine=self.engine,
                        file_path=getattr(rule, "rule_id", None),
                        suggestion="Provide evidence supporting the rule analysis or mark for manual review"
                    ))

        # Check lifecycle for unsupported claims
        lifecycle = self.analysis_result.get("lifecycle")
        if lifecycle:
            confidence = getattr(lifecycle, "confidence", "medium")
            notes = getattr(lifecycle, "notes", [])

            if confidence == "unknown" and not notes:
                issues.append(VerificationIssue(
                    severity="warning",
                    category="unsupported_claims",
                    message="Lifecycle has 'unknown' confidence without notes",
                    engine=self.engine,
                    suggestion="Add notes explaining why lifecycle confidence is unknown"
                ))

        return issues

    def verify_all(self) -> VerificationResult:
        """Run all verification checks and return combined result.

        This is a convenience method that runs all verification methods
        and combines the results into a single VerificationResult.

        Returns:
            VerificationResult with all issues and statistics.
        """
        all_issues: List[VerificationIssue] = []
        checked_items = 0

        # Verify rules
        rules = self.analysis_result.get("rules", [])
        if rules:
            all_issues.extend(self.verify_rules(rules))
            checked_items += len(rules)

        # Verify framework
        framework = self.analysis_result.get("framework")
        if framework:
            all_issues.extend(self.verify_evidence(framework))
            checked_items += 1

        # Verify lifecycle
        lifecycle = self.analysis_result.get("lifecycle")
        if lifecycle:
            all_issues.extend(self.verify_lifecycle(lifecycle))
            checked_items += 1

        # Check unsupported claims
        all_issues.extend(self.check_unsupported_claims())

        # Calculate statistics
        error_count = sum(1 for i in all_issues if i.severity == "error")
        warning_count = sum(1 for i in all_issues if i.severity == "warning")

        return VerificationResult(
            engine=self.engine,
            passed=error_count == 0,
            issues=all_issues,
            checked_items=checked_items,
            warnings=warning_count,
            errors=error_count
        )