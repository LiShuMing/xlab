# Optimizer Expert Analyzer Agent - Phase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Build Comparison Agent, Verifier Agent, and Matrix/Report generation for multi-engine optimizer comparison.

**Architecture:** Comparison agents that cross-reference analysis results, verify correctness, and generate comparison matrices and final reports.

**Tech Stack:** Python 3.10+, pydantic, pandas (for matrix), pathlib

---

## File Structure

```
optimizer_analysis/
  agents/
    comparison_agent.py    # Multi-engine comparison
    verifier_agent.py      # Verify analysis correctness
  comparison/
    __init__.py
    matrix.py              # Matrix generation
    report.py              # Report generation
  schemas/
    comparison.py          # Comparison result schemas
tests/
  test_agents/
    test_comparison_agent.py
    test_verifier_agent.py
  test_comparison/
    test_matrix.py
    test_report.py
```

---

### Task 1: Comparison Schemas

**Files:**
- Create: `optimizer_analysis/schemas/comparison.py`
- Test: `tests/test_schemas/test_comparison.py`

**Requirements:**

```python
class ComparisonDimension(str, Enum):
    """Dimensions for optimizer comparison."""
    LIFECYCLE = "lifecycle"
    RULE_COVERAGE = "rule_coverage"
    PROPERTY_SYSTEM = "property_system"
    STATS_COST = "stats_cost"
    OBSERVABILITY = "observability"
    EXTENSIBILITY = "extensibility"

class ComparisonCell(BaseModel):
    """Single cell in comparison matrix."""
    engine: str
    dimension: ComparisonDimension
    value: str  # "yes", "no", "partial", "explicit", "implicit", "n/a"
    details: Optional[str] = None
    evidence: List[Evidence] = Field(default_factory=list)

class ComparisonMatrix(BaseModel):
    """Full comparison matrix."""
    engines: List[str]
    dimensions: List[ComparisonDimension]
    cells: List[ComparisonCell]
    generated_at: datetime = Field(default_factory=datetime.now)

class ComparisonReport(BaseModel):
    """Final comparison report."""
    title: str
    engines_compared: List[str]
    matrices: List[ComparisonMatrix]
    findings: List[str]
    recommendations: List[str]
```

---

### Task 2: Matrix Generation

**Files:**
- Create: `optimizer_analysis/comparison/__init__.py`
- Create: `optimizer_analysis/comparison/matrix.py`
- Test: `tests/test_comparison/test_matrix.py`

**Requirements:**

```python
class MatrixGenerator:
    """Generate comparison matrices from analysis results."""
    
    def __init__(self, engines_data: Dict[str, Dict]):
        self.engines_data = engines_data
    
    def generate_lifecycle_matrix(self) -> ComparisonMatrix:
        """Generate lifecycle comparison matrix."""
        pass
    
    def generate_rule_coverage_matrix(self) -> ComparisonMatrix:
        """Generate rule coverage comparison matrix."""
        pass
    
    def generate_property_matrix(self) -> ComparisonMatrix:
        """Generate property system comparison matrix."""
        pass
    
    def generate_observability_matrix(self) -> ComparisonMatrix:
        """Generate observability comparison matrix."""
        pass
    
    def generate_all_matrices(self) -> List[ComparisonMatrix]:
        """Generate all comparison matrices."""
        return [
            self.generate_lifecycle_matrix(),
            self.generate_rule_coverage_matrix(),
            self.generate_property_matrix(),
            self.generate_observability_matrix(),
        ]
    
    def to_dataframe(self, matrix: ComparisonMatrix) -> "pandas.DataFrame":
        """Convert matrix to pandas DataFrame."""
        pass
    
    def to_csv(self, matrix: ComparisonMatrix, path: str) -> None:
        """Export matrix to CSV."""
        pass
```

---

### Task 3: Report Generation

**Files:**
- Create: `optimizer_analysis/comparison/report.py`
- Test: `tests/test_comparison/test_report.py`

**Requirements:**

```python
class ReportGenerator:
    """Generate comparison reports."""
    
    def __init__(self, matrices: List[ComparisonMatrix]):
        self.matrices = matrices
    
    def generate_markdown_report(self) -> str:
        """Generate Markdown formatted report."""
        pass
    
    def generate_json_report(self) -> str:
        """Generate JSON formatted report."""
        pass
    
    def identify_findings(self) -> List[str]:
        """Identify key findings from matrices."""
        pass
    
    def generate_recommendations(self) -> List[str]:
        """Generate recommendations based on analysis."""
        pass
    
    def save_report(self, path: str, format: str = "markdown") -> None:
        """Save report to file."""
        pass
```

---

### Task 4: Comparison Agent

**Files:**
- Create: `optimizer_analysis/agents/comparison_agent.py`
- Test: `tests/test_agents/test_comparison_agent.py`

**Requirements:**

```python
class ComparisonAgent(BaseAgent):
    """Agent for comparing multiple engine analyses."""
    
    name = "ComparisonAgent"
    
    def __init__(
        self,
        engines: List[str],
        work_dir: str,
        analysis_results: Dict[str, Dict]
    ):
        super().__init__("comparison", work_dir)
        self.engines = engines
        self.analysis_results = analysis_results
    
    def execute(self) -> AgentResult:
        """Execute comparison analysis."""
        matrices = self.generate_matrices()
        report = self.generate_report(matrices)
        return AgentResult(
            agent_name=self.name,
            status="success",
            artifacts=["comparison/matrix.json", "comparison/report.md"],
            summary=f"Compared {len(self.engines)} engines"
        )
    
    def compare_lifecycles(self) -> ComparisonMatrix:
        """Compare optimizer lifecycles across engines."""
        pass
    
    def compare_rules(self) -> ComparisonMatrix:
        """Compare rule coverage across engines."""
        pass
    
    def compare_properties(self) -> ComparisonMatrix:
        """Compare property systems across engines."""
        pass
```

---

### Task 5: Verifier Agent

**Files:**
- Create: `optimizer_analysis/agents/verifier_agent.py`
- Test: `tests/test_agents/test_verifier_agent.py`

**Requirements:**

```python
class VerificationIssue(BaseModel):
    """Issue found during verification."""
    severity: str  # "error", "warning", "info"
    category: str
    message: str
    engine: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    suggestion: Optional[str] = None

class VerificationResult(BaseModel):
    """Result of verification."""
    engine: str
    passed: bool
    issues: List[VerificationIssue] = Field(default_factory=list)
    checked_items: int = 0
    warnings: int = 0
    errors: int = 0

class VerifierAgent(BaseAgent):
    """Agent for verifying analysis results."""
    
    name = "VerifierAgent"
    
    def __init__(self, engine: str, work_dir: str, analysis_result: Dict, llm_client=None):
        super().__init__(engine, work_dir)
        self.analysis_result = analysis_result
        self.llm_client = llm_client
    
    def execute(self) -> AgentResult:
        """Execute verification."""
        result = self.verify_all()
        return AgentResult(
            agent_name=self.name,
            status="success" if result.passed else "failed",
            artifacts=["verification/result.json"],
            summary=f"Verification: {result.errors} errors, {result.warnings} warnings"
        )
    
    def verify_evidence(self, rule: Rule) -> List[VerificationIssue]:
        """Verify that evidence exists for claims."""
        pass
    
    def verify_lifecycle(self, lifecycle: LifecycleInfo) -> List[VerificationIssue]:
        """Verify lifecycle analysis is complete."""
        pass
    
    def verify_rules(self, rules: List[Rule]) -> List[VerificationIssue]:
        """Verify rule analysis is complete."""
        pass
    
    def check_unsupported_claims(self) -> List[VerificationIssue]:
        """Check for claims without evidence."""
        pass
    
    def verify_all(self) -> VerificationResult:
        """Run all verification checks."""
        pass
```

---

### Task 6: Integration Test

**Files:**
- Create: `tests/test_integration/test_comparison.py`

**Requirements:**

```python
class TestComparisonIntegration:
    """Integration tests for comparison functionality."""
    
    def test_compare_two_engines(self):
        """Test comparing two engine analyses."""
        pass
    
    def test_matrix_generation(self):
        """Test matrix generation from analysis data."""
        pass
    
    def test_report_generation(self):
        """Test report generation."""
        pass
    
    def test_verification_flow(self):
        """Test full verification flow."""
        pass
```

---

### Task 7: Add pandas dependency

**Files:**
- Update: `requirements.txt`

Add `pandas>=2.0.0` for matrix operations.

---

### Task 8: Update Exports and Final Test

**Files:**
- Update: `optimizer_analysis/__init__.py`
- Update: `optimizer_analysis/schemas/__init__.py`
- Update: `optimizer_analysis/agents/__init__.py`
- Update: `optimizer_analysis/comparison/__init__.py`

Run full test suite to verify all Phase 3 components work.

---

## Self-Review Checklist

| DESIGN.md Section | Task Coverage |
|-------------------|---------------|
| Section 7.7 Comparison Agent | Task 4 ✓ |
| Section 7.8 Verifier Agent | Task 5 ✓ |
| Section 8.3 Task 3 Multi-engine Comparison | Tasks 1-4 ✓ |
| Section 10 Reliability | Task 5 ✓ |