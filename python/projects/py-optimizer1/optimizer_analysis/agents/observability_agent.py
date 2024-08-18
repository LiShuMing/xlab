"""Observability Agent for extracting observability/explainability information from optimizer source code."""

import json
import re
from os import makedirs
from os.path import exists, join
from typing import List, Optional, Dict, Any

from optimizer_analysis.agents.base import AgentResult, BaseAgent
from optimizer_analysis.llm_client import ChatMessage
from optimizer_analysis.schemas.base import Evidence, EvidenceType
from optimizer_analysis.schemas.observability import (
    Observability,
    RuleFireVisibility,
)
from optimizer_analysis.scanners.base import CodeFile
from optimizer_analysis.scanners.java_scanner import JavaScanner


# Prompts for observability analysis
EXPLAIN_INTERFACE_PROMPT = """Analyze this code to identify EXPLAIN/EXPLAIN ANALYZE interface implementations.

Engine: {engine}
Code:
```
{code}
```

Please provide a JSON response with the following structure:
{{
    "explain_interfaces": ["list of EXPLAIN command variants supported"],
    "has_explain_analyze": true/false,
    "explain_output_formats": ["list of output formats like TEXT, JSON, XML"],
    "evidence": [
        {{
            "file_path": "path to file",
            "description": "description of what was found",
            "line_start": optional line number,
            "line_end": optional line number,
            "evidence_type": "source_code"
        }}
    ],
    "uncertain_points": ["list of uncertain findings"]
}}

If the code doesn't contain EXPLAIN interface implementations, return:
{{"error": "No EXPLAIN interface found", "reason": "explanation"}}
"""

TRACE_SUPPORT_PROMPT = """Analyze this code to identify trace/debug interface implementations for the optimizer.

Engine: {engine}
Code:
```
{code}
```

Please provide a JSON response with the following structure:
{{
    "trace_interfaces": ["list of trace/debug interfaces"],
    "has_rule_trace": true/false,
    "has_cost_trace": true/false,
    "has_memo_dump": true/false,
    "debug_hooks": ["list of debug hooks or flags"],
    "session_controls": ["list of session-level optimizer control variables"],
    "rule_fire_visibility": "full/partial/none",
    "evidence": [
        {{
            "file_path": "path to file",
            "description": "description of what was found",
            "line_start": optional line number,
            "line_end": optional line number,
            "evidence_type": "source_code"
        }}
    ],
    "uncertain_points": ["list of uncertain findings"]
}}

If the code doesn't contain trace/debug implementations, return:
{{"error": "No trace interface found", "reason": "explanation"}}
"""


class ObservabilityAgent(BaseAgent):
    """Agent for extracting observability/explainability information from optimizer source code.

    This agent analyzes source files to identify and extract:
    - EXPLAIN command implementations
    - Trace/debug interfaces for optimizer inspection
    - Rule fire visibility levels
    - Memo dump support
    - Session-level optimizer controls
    - Debug hooks
    """

    name = "ObservabilityAgent"

    def __init__(
        self,
        engine: str,
        work_dir: str,
        source_path: str,
        llm_client: Optional[object] = None
    ):
        """Initialize the observability agent.

        Args:
            engine: The optimizer engine name.
            work_dir: Working directory for storing artifacts.
            source_path: Path to source files containing observability implementations.
            llm_client: Optional LLM client for enhanced analysis.
        """
        super().__init__(engine, work_dir)
        self.source_path = source_path
        self.llm_client = llm_client

    def execute(self) -> AgentResult:
        """Execute the observability extraction task.

        Scans the source_path for observability-related files and extracts
        EXPLAIN interfaces, trace support, and debug hooks.
        Saves results to observability/index.json.

        Returns:
            AgentResult containing the Observability data and execution status.
        """
        errors: List[str] = []
        artifacts: List[str] = []

        try:
            # Ensure work directory exists
            if not exists(self.work_dir):
                makedirs(self.work_dir, exist_ok=True)

            # Create observability subdirectory
            observability_dir = join(self.work_dir, "observability")
            if not exists(observability_dir):
                makedirs(observability_dir, exist_ok=True)

            # Scan and collect observability information
            observability = self.scan_observability()

            # Save the observability data to index.json
            index_path = join(observability_dir, "index.json")
            observability_data = observability.model_dump()

            with open(index_path, "w") as f:
                json.dump(observability_data, f, indent=2)
            artifacts.append(index_path)

            # Determine status based on findings
            has_findings = (
                len(observability.explain_interfaces) > 0 or
                len(observability.trace_interfaces) > 0 or
                len(observability.debug_hooks) > 0 or
                len(observability.session_controls) > 0
            )

            status = "partial" if errors or not self.llm_client else "success"
            if not has_findings and not self.llm_client:
                status = "partial"

            return AgentResult(
                agent_name=self.name,
                status=status,
                artifacts=artifacts,
                errors=errors,
                summary=(
                    f"Extracted observability information from {self.engine}. "
                    f"Found {len(observability.explain_interfaces)} explain interfaces, "
                    f"{len(observability.trace_interfaces)} trace interfaces, "
                    f"{len(observability.debug_hooks)} debug hooks. "
                    f"Results saved to {index_path}"
                ),
                metadata={
                    "needs_manual_review": not self.llm_client or len(errors) > 0,
                    "explain_interfaces_count": len(observability.explain_interfaces),
                    "trace_interfaces_count": len(observability.trace_interfaces),
                    "debug_hooks_count": len(observability.debug_hooks),
                    "session_controls_count": len(observability.session_controls),
                    "rule_fire_visibility": observability.rule_fire_visibility,
                    "memo_dump_support": observability.memo_dump_support,
                    "has_llm_client": self.llm_client is not None,
                    "source_path": self.source_path,
                }
            )

        except Exception as e:
            errors.append(f"Observability extraction failed: {str(e)}")
            return AgentResult(
                agent_name=self.name,
                status="failed",
                artifacts=artifacts,
                errors=errors,
                summary=f"Observability extraction failed for {self.engine}",
                metadata={"error": str(e)}
            )

    def analyze_explain_interface(self, code_file: CodeFile) -> Dict[str, Any]:
        """Analyze a source file for EXPLAIN interface implementations.

        Args:
            code_file: A CodeFile object containing the source code to analyze.

        Returns:
            Dictionary containing extracted EXPLAIN interface information.

        Raises:
            ValueError: If no LLM client is available.
        """
        if self.llm_client is None:
            raise ValueError("LLM client is required for explain interface analysis")

        user_prompt = EXPLAIN_INTERFACE_PROMPT.format(
            engine=self.engine,
            code=code_file.content
        )

        response = self.llm_client.chat([
            ChatMessage(role="user", content=user_prompt),
        ])

        result = self._parse_llm_response(response)

        if result is None or "error" in result:
            return {}

        # Add evidence if not provided
        if "evidence" not in result or not result["evidence"]:
            result["evidence"] = [
                {
                    "file_path": code_file.path,
                    "description": "Source file analyzed for EXPLAIN interface",
                    "evidence_type": "source_code"
                }
            ]

        return result

    def analyze_trace_support(self, code_file: CodeFile) -> Dict[str, Any]:
        """Analyze a source file for trace/debug interface implementations.

        Args:
            code_file: A CodeFile object containing the source code to analyze.

        Returns:
            Dictionary containing extracted trace support information.

        Raises:
            ValueError: If no LLM client is available.
        """
        if self.llm_client is None:
            raise ValueError("LLM client is required for trace support analysis")

        user_prompt = TRACE_SUPPORT_PROMPT.format(
            engine=self.engine,
            code=code_file.content
        )

        response = self.llm_client.chat([
            ChatMessage(role="user", content=user_prompt),
        ])

        result = self._parse_llm_response(response)

        if result is None or "error" in result:
            return {}

        # Add evidence if not provided
        if "evidence" not in result or not result["evidence"]:
            result["evidence"] = [
                {
                    "file_path": code_file.path,
                    "description": "Source file analyzed for trace support",
                    "evidence_type": "source_code"
                }
            ]

        return result

    def scan_observability(self) -> Observability:
        """Scan the source path and extract observability information.

        Returns:
            Observability object containing all extracted information.
        """
        explain_interfaces: List[str] = []
        trace_interfaces: List[str] = []
        rule_fire_visibility = RuleFireVisibility.NONE
        memo_dump_support = False
        session_controls: List[str] = []
        debug_hooks: List[str] = []
        evidence: List[Evidence] = []
        uncertain_points: List[str] = []

        # Check if path exists
        if not exists(self.source_path):
            uncertain_points.append(f"Source path does not exist: {self.source_path}")
            return Observability(
                explain_interfaces=explain_interfaces,
                trace_interfaces=trace_interfaces,
                rule_fire_visibility=rule_fire_visibility.value,
                memo_dump_support=memo_dump_support,
                session_controls=session_controls,
                debug_hooks=debug_hooks,
                evidence=evidence,
                uncertain_points=uncertain_points
            )

        # Use JavaScanner to scan the path
        scanner = JavaScanner()
        scan_result = scanner.scan_directory(self.source_path)

        # Process each file
        for code_file in scan_result.code_files:
            if not self._is_observability_file(code_file):
                continue

            try:
                if self.llm_client is not None:
                    # Analyze for explain interfaces
                    explain_result = self.analyze_explain_interface(code_file)
                    if explain_result:
                        explain_interfaces.extend(
                            explain_result.get("explain_interfaces", [])
                        )
                        for ev_data in explain_result.get("evidence", []):
                            evidence.append(self._create_evidence(ev_data, code_file))
                        uncertain_points.extend(
                            explain_result.get("uncertain_points", [])
                        )

                    # Analyze for trace support
                    trace_result = self.analyze_trace_support(code_file)
                    if trace_result:
                        trace_interfaces.extend(
                            trace_result.get("trace_interfaces", [])
                        )
                        debug_hooks.extend(
                            trace_result.get("debug_hooks", [])
                        )
                        session_controls.extend(
                            trace_result.get("session_controls", [])
                        )

                        # Check for memo dump support
                        if trace_result.get("has_memo_dump", False):
                            memo_dump_support = True

                        # Update rule fire visibility
                        visibility = trace_result.get("rule_fire_visibility", "none")
                        if visibility == "full":
                            rule_fire_visibility = RuleFireVisibility.FULL
                        elif visibility == "partial" and rule_fire_visibility != RuleFireVisibility.FULL:
                            rule_fire_visibility = RuleFireVisibility.PARTIAL

                        for ev_data in trace_result.get("evidence", []):
                            evidence.append(self._create_evidence(ev_data, code_file))
                        uncertain_points.extend(
                            trace_result.get("uncertain_points", [])
                        )
                else:
                    # Without LLM, create placeholder evidence
                    evidence.append(Evidence(
                        file_path=code_file.path,
                        description="Potential observability file pending LLM analysis",
                        evidence_type=EvidenceType.SOURCE_CODE,
                    ))
                    uncertain_points.append(
                        f"Requires LLM analysis for {code_file.path}"
                    )

                    # Try basic pattern matching for common patterns
                    basic_findings = self._extract_basic_patterns(code_file)
                    explain_interfaces.extend(basic_findings.get("explain_interfaces", []))
                    trace_interfaces.extend(basic_findings.get("trace_interfaces", []))
                    debug_hooks.extend(basic_findings.get("debug_hooks", []))
                    session_controls.extend(basic_findings.get("session_controls", []))

                    if basic_findings.get("memo_dump_support", False):
                        memo_dump_support = True

            except Exception:
                # Skip files that fail analysis
                continue

        # Deduplicate lists
        explain_interfaces = list(set(explain_interfaces))
        trace_interfaces = list(set(trace_interfaces))
        debug_hooks = list(set(debug_hooks))
        session_controls = list(set(session_controls))

        return Observability(
            explain_interfaces=explain_interfaces,
            trace_interfaces=trace_interfaces,
            rule_fire_visibility=rule_fire_visibility.value,
            memo_dump_support=memo_dump_support,
            session_controls=session_controls,
            debug_hooks=debug_hooks,
            evidence=evidence,
            uncertain_points=uncertain_points
        )

    def _parse_llm_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse JSON response from LLM.

        Args:
            response: Raw response string from LLM.

        Returns:
            Parsed dictionary or None if parsing fails.
        """
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                return None
        return None

    def _create_evidence(self, ev_data: Dict[str, Any], code_file: CodeFile) -> Evidence:
        """Create Evidence object from parsed data.

        Args:
            ev_data: Evidence data dictionary from LLM response.
            code_file: The source CodeFile being analyzed.

        Returns:
            An Evidence object.
        """
        return Evidence(
            file_path=ev_data.get("file_path", code_file.path),
            description=ev_data.get("description", ""),
            line_start=ev_data.get("line_start"),
            line_end=ev_data.get("line_end"),
            evidence_type=EvidenceType(ev_data.get("evidence_type", "source_code")),
        )

    def _is_observability_file(self, code_file: CodeFile) -> bool:
        """Check if a file contains observability-related code.

        Observability files typically have these characteristics:
        - Class names containing 'Explain', 'Trace', 'Debug', 'Memo'
        - References to session controls, optimizer variables
        - Located in explain/trace/debug-related directories

        Args:
            code_file: A CodeFile object to check.

        Returns:
            True if the file appears to be observability-related.
        """
        path_lower = code_file.path.lower()
        content_lower = code_file.content.lower()

        # Check for observability indicators in path
        path_indicators = [
            "explain", "trace", "debug", "memo", "observability",
            "dump", "profile", "log", "monitor"
        ]
        has_path_indicator = any(ind in path_lower for ind in path_indicators)

        # Check for observability indicators in content
        content_indicators = [
            "explain", "explain analyze", "trace", "debug",
            "memo dump", "session", "optimizer_", "rule_fire",
            "cost_trace", "plan_trace", "verbose", "profile"
        ]
        has_content_indicator = any(ind in content_lower for ind in content_indicators)

        return has_path_indicator or has_content_indicator

    def _extract_basic_patterns(self, code_file: CodeFile) -> Dict[str, Any]:
        """Extract basic observability patterns without LLM.

        This method performs simple pattern matching to find
        common observability patterns in the code.

        Args:
            code_file: A CodeFile object to analyze.

        Returns:
            Dictionary with extracted patterns.
        """
        result = {
            "explain_interfaces": [],
            "trace_interfaces": [],
            "debug_hooks": [],
            "session_controls": [],
            "memo_dump_support": False,
        }

        content = code_file.content
        content_lower = content.lower()

        # Look for EXPLAIN patterns
        explain_patterns = [
            r"EXPLAIN\s+ANALYZE",
            r"EXPLAIN\s+VERBOSE",
            r"EXPLAIN\s+JSON",
            r"EXPLAIN\s+LOGICAL",
            r"class\s+Explain",
            r"class\s+ExplainAnalyzer",
        ]
        for pattern in explain_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                matched = re.search(pattern, content, re.IGNORECASE)
                if matched:
                    result["explain_interfaces"].append(matched.group().upper())

        # Look for trace patterns
        trace_patterns = [
            r"trace\s*=",
            r"optimizer_trace",
            r"plan_trace",
            r"rule_trace",
            r"cost_trace",
        ]
        for pattern in trace_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                matched = re.search(pattern, content, re.IGNORECASE)
                if matched:
                    result["trace_interfaces"].append(matched.group().strip())

        # Look for debug hooks
        debug_patterns = [
            r"debug\s*mode",
            r"debug\s*flag",
            r"optimizer_debug",
            r"@debug",
            r"DEBUG_",
        ]
        for pattern in debug_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                matched = re.search(pattern, content, re.IGNORECASE)
                if matched:
                    result["debug_hooks"].append(matched.group().strip())

        # Look for session controls
        session_patterns = [
            r"set\s+optimizer",
            r"session\s*\.\s*optimizer",
            r"optimizer_mode",
            r"optimizer_cost",
            r"enable_optimizer",
        ]
        for pattern in session_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                matched = re.search(pattern, content, re.IGNORECASE)
                if matched:
                    result["session_controls"].append(matched.group().strip())

        # Check for memo dump
        if "memo" in content_lower and "dump" in content_lower:
            result["memo_dump_support"] = True

        return result