"""Rule Miner Agent for extracting optimization rules from source code."""

import json
import re
from os import makedirs
from os.path import exists, join
from typing import List, Optional

from pydantic import BaseModel, Field

from optimizer_analysis.agents.base import AgentResult, BaseAgent
from optimizer_analysis.llm_client import ChatMessage
from optimizer_analysis.prompts.rule_prompts import (
    CBO_RULE_PROMPT,
    RBO_RULE_PROMPT,
    RULE_EXTRACTION_SYSTEM_PROMPT,
    RULE_EXTRACTION_USER_PROMPT,
)
from optimizer_analysis.schemas.base import Evidence, EvidenceType
from optimizer_analysis.schemas.rule import ImplementationType, Rule, RuleCategory
from optimizer_analysis.scanners.base import CodeFile
from optimizer_analysis.scanners.java_scanner import JavaScanner


class RuleMiningResult(BaseModel):
    """Result of mining rules from source code.

    This model captures the rules discovered during analysis,
    along with metadata about the mining process.
    """

    engine: str = Field(..., description="Name of the optimizer engine")
    category: RuleCategory = Field(..., description="Category of rules being mined")
    rules_found: int = Field(
        0,
        description="Number of rules found in this category"
    )
    rules: List[Rule] = Field(
        default_factory=list,
        description="List of discovered rules"
    )
    confidence: str = Field(
        "medium",
        description="Confidence level of the analysis: high, medium, low, unknown"
    )
    notes: List[str] = Field(
        default_factory=list,
        description="Additional notes about the mining process"
    )


class RuleMinerAgent(BaseAgent):
    """Agent for mining optimization rules from source code.

    This agent analyzes source files to identify and extract
    optimization rules belonging to a specific category.
    """

    name = "RuleMiner"

    def __init__(
        self,
        engine: str,
        work_dir: str,
        category: RuleCategory,
        source_path: str,
        llm_client: Optional[object] = None
    ):
        """Initialize the rule miner agent.

        Args:
            engine: The optimizer engine name.
            work_dir: Working directory for storing artifacts.
            category: The rule category to mine (RBO, CBO, etc.).
            source_path: Path to source files containing rules.
            llm_client: Optional LLM client for enhanced analysis.
        """
        super().__init__(engine, work_dir)
        self.category = category
        self.source_path = source_path
        self.llm_client = llm_client

    def execute(self) -> AgentResult:
        """Execute the rule mining task.

        Returns:
            AgentResult containing the RuleMiningResult and execution status.
            The status is 'partial' with needs_manual_review=True since
            rule mining requires domain expertise and code analysis.
        """
        errors: List[str] = []
        artifacts: List[str] = []

        try:
            # Ensure work directory exists
            if not exists(self.work_dir):
                makedirs(self.work_dir, exist_ok=True)

            # Create rules subdirectory
            rules_dir = join(self.work_dir, "rules")
            if not exists(rules_dir):
                makedirs(rules_dir, exist_ok=True)

            # Create initial mining result with placeholder values
            # This indicates the analysis needs manual review and completion
            mining_result = RuleMiningResult(
                engine=self.engine,
                category=self.category,
                rules_found=0,
                rules=[],
                confidence="low",
                notes=[
                    "Initial rule mining structure created.",
                    "This analysis requires manual review and completion.",
                    f"Target category: {self.category.value}",
                    f"Source path: {self.source_path}",
                    "Identify rule implementations in source code.",
                    "Document rule registration points.",
                    "Extract transformation logic patterns.",
                    "Mark confidence as 'high' after verification.",
                ]
            )

            # Add LLM availability note
            if self.llm_client is not None:
                mining_result.notes.append(
                    "LLM client available for enhanced analysis."
                )
            else:
                mining_result.notes.append(
                    "No LLM client provided. Manual analysis required."
                )

            # Save the mining result as JSON artifact
            category_filename = f"{self.category.value}_rules.json"
            rules_json_path = join(rules_dir, category_filename)
            with open(rules_json_path, "w") as f:
                f.write(mining_result.model_dump_json(indent=2))
            artifacts.append(rules_json_path)

            return AgentResult(
                agent_name=self.name,
                status="partial",
                artifacts=artifacts,
                errors=errors,
                summary=(
                    f"Created initial rule mining result for {self.engine} "
                    f"category {self.category.value}. "
                    f"Requires manual review to identify actual rules. "
                    f"Mining result saved to {rules_json_path}"
                ),
                metadata={
                    "needs_manual_review": True,
                    "confidence": "low",
                    "category": self.category.value,
                    "rules_found": 0,
                    "has_llm_client": self.llm_client is not None
                }
            )

        except Exception as e:
            errors.append(f"Failed to create rule mining result: {str(e)}")
            return AgentResult(
                agent_name=self.name,
                status="failed",
                artifacts=artifacts,
                errors=errors,
                summary=f"Rule mining failed for {self.engine} category {self.category.value}",
                metadata={
                    "error": str(e)
                }
            )

    def extract_rule_from_code(self, code_file: CodeFile) -> Optional[Rule]:
        """Extract a Rule object from a CodeFile using LLM analysis.

        This method uses the LLM client to analyze the source code and
        extract structured information about optimization rules.

        Args:
            code_file: A CodeFile object containing the source code to analyze.

        Returns:
            A Rule object if extraction is successful, None otherwise.

        Raises:
            ValueError: If no LLM client is available.
        """
        if self.llm_client is None:
            raise ValueError("LLM client is required for rule extraction")

        # Select appropriate prompt based on category
        if self.category == RuleCategory.RBO:
            user_prompt = RBO_RULE_PROMPT.format(
                engine=self.engine,
                code=code_file.content
            )
        elif self.category == RuleCategory.CBO:
            user_prompt = CBO_RULE_PROMPT.format(
                engine=self.engine,
                code=code_file.content
            )
        else:
            user_prompt = RULE_EXTRACTION_USER_PROMPT.format(
                engine=self.engine,
                category=self.category.value,
                code=code_file.content
            )

        # Call LLM with the appropriate prompt
        response = self.llm_client.chat([
            ChatMessage(role="system", content=RULE_EXTRACTION_SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_prompt),
        ])

        # Parse the JSON response
        rule_data = self._parse_llm_response(response)

        if rule_data is None or "error" in rule_data:
            return None

        # Create Rule object from parsed data
        return self._create_rule_from_data(rule_data, code_file)

    def _parse_llm_response(self, response: str) -> Optional[dict]:
        """Parse JSON response from LLM.

        Args:
            response: Raw response string from LLM.

        Returns:
            Parsed dictionary or None if parsing fails.
        """
        # Try to extract JSON from response
        # Handle cases where LLM might include extra text
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                return None
        return None

    def _create_rule_from_data(
        self,
        rule_data: dict,
        code_file: CodeFile
    ) -> Rule:
        """Create a Rule object from parsed LLM response data.

        Args:
            rule_data: Parsed dictionary from LLM response.
            code_file: The source CodeFile being analyzed.

        Returns:
            A Rule object populated with extracted data.
        """
        # Parse evidence from response
        evidence_list = []
        for ev_data in rule_data.get("evidence", []):
            evidence_list.append(Evidence(
                file_path=ev_data.get("file_path", code_file.path),
                description=ev_data.get("description", ""),
                line_start=ev_data.get("line_start"),
                line_end=ev_data.get("line_end"),
                evidence_type=EvidenceType(ev_data.get("evidence_type", "source_code")),
            ))

        # Add default evidence pointing to the analyzed file
        if not evidence_list:
            evidence_list.append(Evidence(
                file_path=code_file.path,
                description="Source file analyzed for rule extraction",
                evidence_type=EvidenceType.SOURCE_CODE,
            ))

        # Determine implementation type
        impl_type_str = rule_data.get("implementation_type", "explicitly_implemented")
        impl_type = ImplementationType(impl_type_str)

        # Create Rule object
        return Rule(
            rule_id=rule_data.get("rule_id", "UNKNOWN"),
            rule_name=rule_data.get("rule_name", "Unknown Rule"),
            engine=self.engine,
            rule_category=self.category,
            implementation_type=impl_type,
            lifecycle_stage=rule_data.get("lifecycle_stage"),
            source_files=rule_data.get("source_files", [code_file.path]),
            registration_points=rule_data.get("registration_points", []),
            trigger_pattern=rule_data.get("trigger_pattern"),
            preconditions=rule_data.get("preconditions", []),
            transformation_logic=rule_data.get("transformation_logic"),
            input_operators=rule_data.get("input_operators", []),
            output_operators=rule_data.get("output_operators", []),
            relational_algebra_form=rule_data.get("relational_algebra_form"),
            depends_on_stats=rule_data.get("depends_on_stats", False),
            depends_on_cost=rule_data.get("depends_on_cost", False),
            depends_on_property=rule_data.get("depends_on_property", False),
            examples=rule_data.get("examples", []),
            confidence=rule_data.get("confidence", "medium"),
            uncertain_points=rule_data.get("uncertain_points", []),
            evidence=evidence_list,
        )


class RBOMinerAgent(RuleMinerAgent):
    """Specialized miner for Rule-Based Optimization (RBO) rules.

    This agent scans Java source files to identify and extract
    RBO rules - rules that apply transformations based on pattern
    matching without cost-based decisions.
    """

    name = "RBOMiner"

    def __init__(
        self,
        engine: str,
        work_dir: str,
        source_path: str,
        llm_client: Optional[object] = None
    ):
        """Initialize the RBO rule miner agent.

        Args:
            engine: The optimizer engine name.
            work_dir: Working directory for storing artifacts.
            source_path: Path to source files containing RBO rules.
            llm_client: Optional LLM client for enhanced analysis.
        """
        super().__init__(engine, work_dir, RuleCategory.RBO, source_path, llm_client)

    def execute(self) -> AgentResult:
        """Execute the RBO rule mining task.

        Scans the source_path for Java files and filters for RBO rules.
        Saves results to the appropriate artifact path.

        Returns:
            AgentResult containing the RuleMiningResult and execution status.
        """
        errors: List[str] = []
        artifacts: List[str] = []
        rules: List[Rule] = []

        try:
            # Ensure work directory exists
            if not exists(self.work_dir):
                makedirs(self.work_dir, exist_ok=True)

            # Create rules subdirectory
            rules_dir = join(self.work_dir, "rules")
            if not exists(rules_dir):
                makedirs(rules_dir, exist_ok=True)

            # Use JavaScanner to scan source_path
            scanner = JavaScanner()
            scan_result = scanner.scan_directory(self.source_path)

            # Track any scan errors
            if scan_result.errors:
                errors.extend(scan_result.errors)

            # Filter and extract RBO rules from each file
            for code_file in scan_result.code_files:
                try:
                    # Skip files that don't appear to be RBO rules
                    if not self._is_rbo_rule({"content": code_file.content, "path": code_file.path}):
                        continue

                    # If LLM client is available, extract structured rule
                    if self.llm_client is not None:
                        rule = self.extract_rule_from_code(code_file)
                        if rule is not None:
                            rules.append(rule)
                    else:
                        # Without LLM, create placeholder entry
                        rules.append(Rule(
                            rule_id=f"RBO_PLACEHOLDER_{len(rules) + 1}",
                            rule_name="RBO Rule (Pending Analysis)",
                            engine=self.engine,
                            rule_category=RuleCategory.RBO,
                            source_files=[code_file.path],
                            confidence="low",
                            uncertain_points=["Requires LLM analysis for full extraction"]
                        ))

                except Exception as e:
                    errors.append(f"Failed to process {code_file.path}: {str(e)}")

            # Create mining result
            mining_result = RuleMiningResult(
                engine=self.engine,
                category=RuleCategory.RBO,
                rules_found=len(rules),
                rules=rules,
                confidence="low" if not self.llm_client else "medium",
                notes=[
                    f"Scanned {scan_result.files_scanned} Java files",
                    f"Identified {len(rules)} potential RBO rules",
                    f"Source path: {self.source_path}",
                    "Manual review recommended for rule verification",
                ]
            )

            # Save the mining result
            rules_json_path = join(rules_dir, "rbo_rules.json")
            with open(rules_json_path, "w") as f:
                f.write(mining_result.model_dump_json(indent=2))
            artifacts.append(rules_json_path)

            return AgentResult(
                agent_name=self.name,
                status="partial" if errors or not self.llm_client else "success",
                artifacts=artifacts,
                errors=errors,
                summary=(
                    f"Mined {len(rules)} RBO rules from {self.engine}. "
                    f"Scanned {scan_result.files_scanned} files. "
                    f"Results saved to {rules_json_path}"
                ),
                metadata={
                    "needs_manual_review": not self.llm_client or len(errors) > 0,
                    "confidence": mining_result.confidence,
                    "category": RuleCategory.RBO.value,
                    "rules_found": len(rules),
                    "files_scanned": scan_result.files_scanned,
                    "has_llm_client": self.llm_client is not None
                }
            )

        except Exception as e:
            errors.append(f"RBO rule mining failed: {str(e)}")
            return AgentResult(
                agent_name=self.name,
                status="failed",
                artifacts=artifacts,
                errors=errors,
                summary=f"RBO rule mining failed for {self.engine}",
                metadata={"error": str(e)}
            )

    def _is_rbo_rule(self, rule_dict: dict) -> bool:
        """Check if a file contains an RBO rule.

        RBO rules typically have these characteristics:
        - Class names ending with 'Rule' or containing 'Transform'
        - No references to cost model or statistics
        - Pattern-based transformation logic

        Args:
            rule_dict: Dictionary containing file content and path.

        Returns:
            True if the file appears to be an RBO rule.
        """
        content = rule_dict.get("content", "")
        path = rule_dict.get("path", "")

        # Check file path/name patterns
        path_lower = path.lower()
        content_lower = content.lower()

        # RBO rules typically don't depend on cost model - check this first
        has_cost_dependency = any(pattern in content_lower for pattern in [
            "costmodel", "costmodel", "statistics", "stats", "estimatedcost",
            "costestimate", "compute_cost"
        ])

        # If content has cost dependency, it's likely a CBO rule, not RBO
        if has_cost_dependency:
            return False

        # RBO rules typically have pattern matching
        has_pattern_matching = any(pattern in content_lower for pattern in [
            "pattern", "matches", "transform", "rewrite", "replace"
        ])

        # Check if file looks like a rule file
        looks_like_rule = any(pattern in path_lower for pattern in ["rule", "transform", "rewrite", "opt"])

        # If it looks like a rule file and has pattern matching, it's likely RBO
        if looks_like_rule and has_pattern_matching:
            return True

        # If file is in RBO-specific directory
        if any(pattern in path_lower for pattern in ["rbo", "logicalrule"]):
            return True

        return False


class CBOMinerAgent(RuleMinerAgent):
    """Specialized miner for Cost-Based Optimization (CBO) rules.

    This agent scans Java source files to identify and extract
    CBO rules - rules that make decisions based on cost model
    calculations and statistics.
    """

    name = "CBOMiner"
    category = RuleCategory.CBO

    def __init__(
        self,
        engine: str,
        work_dir: str,
        source_path: str,
        llm_client: Optional[object] = None
    ):
        """Initialize the CBO rule miner agent.

        Args:
            engine: The optimizer engine name.
            work_dir: Working directory for storing artifacts.
            source_path: Path to source files containing CBO rules.
            llm_client: Optional LLM client for enhanced analysis.
        """
        super().__init__(engine, work_dir, RuleCategory.CBO, source_path, llm_client)

    def execute(self) -> AgentResult:
        """Execute the CBO rule mining task.

        Scans the source_path for Java files and filters for CBO rules.
        Saves results to the appropriate artifact path.

        Returns:
            AgentResult containing the RuleMiningResult and execution status.
        """
        errors: List[str] = []
        artifacts: List[str] = []
        rules: List[Rule] = []

        try:
            # Ensure work directory exists
            if not exists(self.work_dir):
                makedirs(self.work_dir, exist_ok=True)

            # Create rules subdirectory
            rules_dir = join(self.work_dir, "rules")
            if not exists(rules_dir):
                makedirs(rules_dir, exist_ok=True)

            # Use JavaScanner to scan source_path
            scanner = JavaScanner()
            scan_result = scanner.scan_directory(self.source_path)

            # Track any scan errors
            if scan_result.errors:
                errors.extend(scan_result.errors)

            # Filter and extract CBO rules from each file
            for code_file in scan_result.code_files:
                try:
                    # Skip files that don't appear to be CBO rules
                    if not self._is_cbo_rule({"content": code_file.content, "path": code_file.path}):
                        continue

                    # If LLM client is available, extract structured rule
                    if self.llm_client is not None:
                        rule = self.extract_rule_from_code(code_file)
                        if rule is not None:
                            rules.append(rule)
                    else:
                        # Without LLM, create placeholder entry
                        rules.append(Rule(
                            rule_id=f"CBO_PLACEHOLDER_{len(rules) + 1}",
                            rule_name="CBO Rule (Pending Analysis)",
                            engine=self.engine,
                            rule_category=RuleCategory.CBO,
                            source_files=[code_file.path],
                            depends_on_cost=True,
                            depends_on_stats=True,
                            confidence="low",
                            uncertain_points=["Requires LLM analysis for full extraction"]
                        ))

                except Exception as e:
                    errors.append(f"Failed to process {code_file.path}: {str(e)}")

            # Create mining result
            mining_result = RuleMiningResult(
                engine=self.engine,
                category=RuleCategory.CBO,
                rules_found=len(rules),
                rules=rules,
                confidence="low" if not self.llm_client else "medium",
                notes=[
                    f"Scanned {scan_result.files_scanned} Java files",
                    f"Identified {len(rules)} potential CBO rules",
                    f"Source path: {self.source_path}",
                    "Manual review recommended for rule verification",
                ]
            )

            # Save the mining result
            rules_json_path = join(rules_dir, "cbo_rules.json")
            with open(rules_json_path, "w") as f:
                f.write(mining_result.model_dump_json(indent=2))
            artifacts.append(rules_json_path)

            return AgentResult(
                agent_name=self.name,
                status="partial" if errors or not self.llm_client else "success",
                artifacts=artifacts,
                errors=errors,
                summary=(
                    f"Mined {len(rules)} CBO rules from {self.engine}. "
                    f"Scanned {scan_result.files_scanned} files. "
                    f"Results saved to {rules_json_path}"
                ),
                metadata={
                    "needs_manual_review": not self.llm_client or len(errors) > 0,
                    "confidence": mining_result.confidence,
                    "category": RuleCategory.CBO.value,
                    "rules_found": len(rules),
                    "files_scanned": scan_result.files_scanned,
                    "has_llm_client": self.llm_client is not None
                }
            )

        except Exception as e:
            errors.append(f"CBO rule mining failed: {str(e)}")
            return AgentResult(
                agent_name=self.name,
                status="failed",
                artifacts=artifacts,
                errors=errors,
                summary=f"CBO rule mining failed for {self.engine}",
                metadata={"error": str(e)}
            )

    def _is_cbo_rule(self, rule_dict: dict) -> bool:
        """Check if a file contains a CBO rule.

        CBO rules typically have these characteristics:
        - References to cost model, statistics, or estimation
        - Cost-based decision making logic
        - Join order or plan selection logic

        Args:
            rule_dict: Dictionary containing file content and path.

        Returns:
            True if the file appears to be a CBO rule.
        """
        content = rule_dict.get("content", "")
        path = rule_dict.get("path", "")

        # Check file path/name patterns
        path_lower = path.lower()

        # Check for CBO indicators in content
        content_lower = content.lower()

        # CBO rules typically depend on cost model or statistics
        has_cost_dependency = any(pattern in content_lower for pattern in [
            "costmodel", "costmodel", "statistics", "stats", "statscost",
            "estimatedcost", "estimatedrows", "costestimate", "compute_cost"
        ])

        # CBO-specific patterns like join ordering
        has_cbo_patterns = any(pattern in content_lower for pattern in [
            "joinorder", "planselection", "costbased", "minimumcost",
            "optimalplan", "choosebest"
        ])

        # Check for CBO-specific directories
        in_cbo_directory = any(pattern in path_lower for pattern in [
            "cbo", "cost", "stats", "joinorder", "physicalrule"
        ])

        # If it's in a CBO directory or has cost indicators
        if in_cbo_directory or (has_cost_dependency and has_cbo_patterns):
            return True

        # If file has cost dependency and looks like a rule
        if has_cost_dependency and any(pattern in path_lower for pattern in ["rule", "opt", "plan"]):
            return True

        return False


class ScalarRuleMinerAgent(RuleMinerAgent):
    """Specialized miner for Scalar optimization rules.

    This agent scans Java source files to identify and extract
    scalar rules - rules that optimize scalar expressions and
    subqueries.
    """

    name = "ScalarRuleMiner"

    def __init__(
        self,
        engine: str,
        work_dir: str,
        source_path: str,
        llm_client: Optional[object] = None
    ):
        """Initialize the Scalar rule miner agent.

        Args:
            engine: The optimizer engine name.
            work_dir: Working directory for storing artifacts.
            source_path: Path to source files containing scalar rules.
            llm_client: Optional LLM client for enhanced analysis.
        """
        super().__init__(engine, work_dir, RuleCategory.SCALAR, source_path, llm_client)

    def execute(self) -> AgentResult:
        """Execute the Scalar rule mining task.

        Scans the source_path for Java files and filters for scalar rules.
        Saves results to the appropriate artifact path.

        Returns:
            AgentResult containing the RuleMiningResult and execution status.
        """
        errors: List[str] = []
        artifacts: List[str] = []
        rules: List[Rule] = []

        try:
            # Ensure work directory exists
            if not exists(self.work_dir):
                makedirs(self.work_dir, exist_ok=True)

            # Create rules subdirectory
            rules_dir = join(self.work_dir, "rules")
            if not exists(rules_dir):
                makedirs(rules_dir, exist_ok=True)

            # Use JavaScanner to scan source_path
            scanner = JavaScanner()
            scan_result = scanner.scan_directory(self.source_path)

            # Track any scan errors
            if scan_result.errors:
                errors.extend(scan_result.errors)

            # Filter and extract scalar rules from each file
            for code_file in scan_result.code_files:
                try:
                    # Skip files that don't appear to be scalar rules
                    if not self._is_scalar_rule({"content": code_file.content, "path": code_file.path}):
                        continue

                    # If LLM client is available, extract structured rule
                    if self.llm_client is not None:
                        rule = self.extract_rule_from_code(code_file)
                        if rule is not None:
                            rules.append(rule)
                    else:
                        # Without LLM, create placeholder entry
                        rules.append(Rule(
                            rule_id=f"SCALAR_PLACEHOLDER_{len(rules) + 1}",
                            rule_name="Scalar Rule (Pending Analysis)",
                            engine=self.engine,
                            rule_category=RuleCategory.SCALAR,
                            source_files=[code_file.path],
                            confidence="low",
                            uncertain_points=["Requires LLM analysis for full extraction"]
                        ))

                except Exception as e:
                    errors.append(f"Failed to process {code_file.path}: {str(e)}")

            # Create mining result
            mining_result = RuleMiningResult(
                engine=self.engine,
                category=RuleCategory.SCALAR,
                rules_found=len(rules),
                rules=rules,
                confidence="low" if not self.llm_client else "medium",
                notes=[
                    f"Scanned {scan_result.files_scanned} Java files",
                    f"Identified {len(rules)} potential scalar rules",
                    f"Source path: {self.source_path}",
                    "Manual review recommended for rule verification",
                ]
            )

            # Save the mining result
            rules_json_path = join(rules_dir, "scalar_rules.json")
            with open(rules_json_path, "w") as f:
                f.write(mining_result.model_dump_json(indent=2))
            artifacts.append(rules_json_path)

            return AgentResult(
                agent_name=self.name,
                status="partial" if errors or not self.llm_client else "success",
                artifacts=artifacts,
                errors=errors,
                summary=(
                    f"Mined {len(rules)} scalar rules from {self.engine}. "
                    f"Scanned {scan_result.files_scanned} files. "
                    f"Results saved to {rules_json_path}"
                ),
                metadata={
                    "needs_manual_review": not self.llm_client or len(errors) > 0,
                    "confidence": mining_result.confidence,
                    "category": RuleCategory.SCALAR.value,
                    "rules_found": len(rules),
                    "files_scanned": scan_result.files_scanned,
                    "has_llm_client": self.llm_client is not None
                }
            )

        except Exception as e:
            errors.append(f"Scalar rule mining failed: {str(e)}")
            return AgentResult(
                agent_name=self.name,
                status="failed",
                artifacts=artifacts,
                errors=errors,
                summary=f"Scalar rule mining failed for {self.engine}",
                metadata={"error": str(e)}
            )

    def _is_scalar_rule(self, rule_dict: dict) -> bool:
        """Check if a file contains a scalar rule.

        Scalar rules typically have these characteristics:
        - References to scalar expressions, subqueries
        - Constant folding or expression simplification
        - Arithmetic or function evaluation optimization

        Args:
            rule_dict: Dictionary containing file content and path.

        Returns:
            True if the file appears to be a scalar rule.
        """
        content = rule_dict.get("content", "")
        path = rule_dict.get("path", "")

        path_lower = path.lower()
        content_lower = content.lower()

        # Scalar rule indicators
        has_scalar_patterns = any(pattern in content_lower for pattern in [
            "scalar", "subquery", "constants", "expression",
            "arithmetic", "function", "literal", "fold",
            "simplify", "evaluate"
        ])

        # Check for scalar-specific directories
        in_scalar_directory = any(pattern in path_lower for pattern in [
            "scalar", "expression", "constant", "fold"
        ])

        # If it's in a scalar directory
        if in_scalar_directory:
            return True

        # If file has scalar patterns and looks like a rule file
        if has_scalar_patterns and any(pattern in path_lower for pattern in ["rule", "transform", "opt"]):
            return True

        return False


class PostOptimizerMinerAgent(RuleMinerAgent):
    """Specialized miner for Post-Optimization rules.

    This agent scans Java source files to identify and extract
    post-optimization rules - rules that run after the main
    optimization phase to refine the plan.
    """

    name = "PostOptimizerMiner"

    def __init__(
        self,
        engine: str,
        work_dir: str,
        source_path: str,
        llm_client: Optional[object] = None
    ):
        """Initialize the post-optimizer rule miner agent.

        Args:
            engine: The optimizer engine name.
            work_dir: Working directory for storing artifacts.
            source_path: Path to source files containing post-optimization rules.
            llm_client: Optional LLM client for enhanced analysis.
        """
        super().__init__(engine, work_dir, RuleCategory.POST_OPT, source_path, llm_client)

    def execute(self) -> AgentResult:
        """Execute the post-optimization rule mining task.

        Scans the source_path for Java files and filters for post-opt rules.
        Saves results to the appropriate artifact path.

        Returns:
            AgentResult containing the RuleMiningResult and execution status.
        """
        errors: List[str] = []
        artifacts: List[str] = []
        rules: List[Rule] = []

        try:
            # Ensure work directory exists
            if not exists(self.work_dir):
                makedirs(self.work_dir, exist_ok=True)

            # Create rules subdirectory
            rules_dir = join(self.work_dir, "rules")
            if not exists(rules_dir):
                makedirs(rules_dir, exist_ok=True)

            # Use JavaScanner to scan source_path
            scanner = JavaScanner()
            scan_result = scanner.scan_directory(self.source_path)

            # Track any scan errors
            if scan_result.errors:
                errors.extend(scan_result.errors)

            # Filter and extract post-opt rules from each file
            for code_file in scan_result.code_files:
                try:
                    # Skip files that don't appear to be post-opt rules
                    if not self._is_post_opt_rule({"content": code_file.content, "path": code_file.path}):
                        continue

                    # If LLM client is available, extract structured rule
                    if self.llm_client is not None:
                        rule = self.extract_rule_from_code(code_file)
                        if rule is not None:
                            rules.append(rule)
                    else:
                        # Without LLM, create placeholder entry
                        rules.append(Rule(
                            rule_id=f"POSTOPT_PLACEHOLDER_{len(rules) + 1}",
                            rule_name="Post-Opt Rule (Pending Analysis)",
                            engine=self.engine,
                            rule_category=RuleCategory.POST_OPT,
                            source_files=[code_file.path],
                            confidence="low",
                            uncertain_points=["Requires LLM analysis for full extraction"]
                        ))

                except Exception as e:
                    errors.append(f"Failed to process {code_file.path}: {str(e)}")

            # Create mining result
            mining_result = RuleMiningResult(
                engine=self.engine,
                category=RuleCategory.POST_OPT,
                rules_found=len(rules),
                rules=rules,
                confidence="low" if not self.llm_client else "medium",
                notes=[
                    f"Scanned {scan_result.files_scanned} Java files",
                    f"Identified {len(rules)} potential post-opt rules",
                    f"Source path: {self.source_path}",
                    "Manual review recommended for rule verification",
                ]
            )

            # Save the mining result
            rules_json_path = join(rules_dir, "post_opt_rules.json")
            with open(rules_json_path, "w") as f:
                f.write(mining_result.model_dump_json(indent=2))
            artifacts.append(rules_json_path)

            return AgentResult(
                agent_name=self.name,
                status="partial" if errors or not self.llm_client else "success",
                artifacts=artifacts,
                errors=errors,
                summary=(
                    f"Mined {len(rules)} post-opt rules from {self.engine}. "
                    f"Scanned {scan_result.files_scanned} files. "
                    f"Results saved to {rules_json_path}"
                ),
                metadata={
                    "needs_manual_review": not self.llm_client or len(errors) > 0,
                    "confidence": mining_result.confidence,
                    "category": RuleCategory.POST_OPT.value,
                    "rules_found": len(rules),
                    "files_scanned": scan_result.files_scanned,
                    "has_llm_client": self.llm_client is not None
                }
            )

        except Exception as e:
            errors.append(f"Post-opt rule mining failed: {str(e)}")
            return AgentResult(
                agent_name=self.name,
                status="failed",
                artifacts=artifacts,
                errors=errors,
                summary=f"Post-opt rule mining failed for {self.engine}",
                metadata={"error": str(e)}
            )

    def _is_post_opt_rule(self, rule_dict: dict) -> bool:
        """Check if a file contains a post-optimization rule.

        Post-optimization rules typically have these characteristics:
        - References to post-optimization phase
        - Plan refinement or adjustment logic
        - Late-stage optimization patterns

        Args:
            rule_dict: Dictionary containing file content and path.

        Returns:
            True if the file appears to be a post-optimization rule.
        """
        content = rule_dict.get("content", "")
        path = rule_dict.get("path", "")

        path_lower = path.lower()
        content_lower = content.lower()

        # Post-optimization rule indicators
        has_post_opt_patterns = any(pattern in content_lower for pattern in [
            "postopt", "post_optimize", "postoptimization",
            "refine", "finalize", "adjustplan",
            "lateoptimize", "finalpass"
        ])

        # Check for post-opt specific directories
        in_post_opt_directory = any(pattern in path_lower for pattern in [
            "postopt", "post_opt", "refine", "finalize"
        ])

        # If it's in a post-opt directory
        if in_post_opt_directory:
            return True

        # If file has post-opt patterns
        if has_post_opt_patterns:
            return True

        return False