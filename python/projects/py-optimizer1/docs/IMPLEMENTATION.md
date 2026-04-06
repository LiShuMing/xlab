# Optimizer Expert Analyzer - Implementation Documentation

## Architecture Overview

The Optimizer Expert Analyzer is a modular system designed to analyze query optimizer source code across multiple database engines using LLM-powered semantic analysis.

### Core Components

```
optimizer_analysis/
├── schemas/           # Pydantic schemas for unified data models
│   ├── base.py        # Evidence, AgentContext, Confidence
│   ├── framework.py   # Memo, Group, GroupExpression models
│   ├── rule.py        # Rule, RuleCategory, RuleType
│   ├── trait.py       # Trait, Property, Distribution
│   ├── stats_cost.py  # StatsInfo, CostInfo, CostModel
│   ├── observability.py  # Metrics, ObservabilityInfo
│   ├── extensibility.py  # Extension points, Plugin interfaces
│   └── comparison.py  # ComparisonDimension, ComparisonMatrix
│
├── agents/            # Analysis agents (LLM-powered)
│   ├── base.py        # BaseAgent interface
│   ├── repo_mapper.py # Repository structure mapper
│   ├── lifecycle.py   # Agent lifecycle management
│   ├── rule_miner.py  # Rule extraction agent
│   ├── property_agent.py    # Property/trait analyzer
│   ├── stats_cost_agent.py  # Stats/cost analyzer
│   ├── observability_agent.py # Observability analyzer
│   ├── comparison_agent.py  # Cross-engine comparison
│   └── verifier_agent.py    # Result verification
│
├── scanners/          # Code scanners
│   ├── base.py        # Scanner interface
│   └── java_scanner.py # Java source scanner
│
├── prompts/           # LLM prompts
│   ├── rule_prompts.py     # Rule analysis prompts
│   ├── property_prompts.py # Property prompts
│   └── stats_prompts.py    # Stats prompts
│
├── engines/           # Engine configurations
│   ├── base.py        # EngineConfig base
│   ├── registry.py    # Engine registry
│   └── presets.py     # StarRocks, Calcite, Doris configs
│
├── comparison/        # Comparison utilities
│   ├── matrix.py      # MatrixGenerator
│   └── report.py      # ReportGenerator
│
├── config.py          # Configuration from ~/.env
├── llm_client.py      # LLM client (OpenAI-compatible)
```

## Schema Design

### Base Schema (Evidence Pattern)

All analysis results follow the Evidence pattern for confidence tracking:

```python
class Evidence(BaseModel):
    """Evidence pattern for confidence scoring."""
    source: str              # Where evidence comes from
    confidence: float        # 0.0 to 1.0
    reasoning: str           # Why this evidence matters
    metadata: Dict[str, Any] = {}
```

### Rule Schema

```python
class Rule(BaseModel):
    """Unified rule representation across engines."""
    name: str
    category: RuleCategory      # RBO, CBO, SCALAR, etc.
    type: RuleType              # TRANSFORMATION, IMPLEMENTATION
    description: str
    input_pattern: str          # Operator pattern to match
    output_pattern: str         # Result pattern
    relational_algebra: str     # σ, π, ⋈, γ, τ expressions
    dependencies: List[str]     # Required stats/cost/properties
    benefits: List[str]         # Optimization benefits
    evidence: Evidence          # Analysis confidence
```

## Agent Design

### BaseAgent Interface

```python
class BaseAgent(ABC):
    """Abstract base for all analysis agents."""
    
    @abstractmethod
    async def analyze(self, context: AgentContext) -> List[Evidence]:
        """Perform analysis and return evidence."""
        pass
    
    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """Return agent capabilities."""
        pass
```

### Rule Miner Agent

Uses LLM to extract semantic rule information:

```python
class RuleMinerAgent(BaseAgent):
    """Extract rules from source code using LLM."""
    
    def analyze(self, context: AgentContext) -> List[Evidence]:
        # 1. Scan source code for rule classes
        # 2. Send to LLM for semantic analysis
        # 3. Parse LLM response into Rule schema
        # 4. Return evidence with confidence score
```

## Engine Configuration

### Supported Engines

```python
# StarRocks - Cascades optimizer
STARROCKS_CONFIG = EngineConfig(
    name="StarRocks",
    engine_type=EngineType.COLUMNAR_OLAP,
    optimizer_style=OptimizerStyle.CASCADES,
    optimizer_dirs=["fe/fe-core/src/main/java/com/starrocks/sql/optimizer"],
    main_entry="fe/fe-core/src/main/java/com/starrocks/sql/optimizer/Optimizer.java",
)

# Apache Calcite - Volcano framework
CALCITE_CONFIG = EngineConfig(
    name="Calcite",
    engine_type=EngineType.FRAMEWORK,
    optimizer_style=OptimizerStyle.VOLCANO,
    optimizer_dirs=["core/src/main/java/org/apache/calcite/rel/rules"],
)

# Apache Doris - Cascades optimizer
DORIS_CONFIG = EngineConfig(
    name="Doris",
    engine_type=EngineType.COLUMNAR_OLAP,
    optimizer_style=OptimizerStyle.CASCADES,
    optimizer_dirs=["fe/fe-core/src/main/java/org/apache/doris/nereids/rules"],
)
```

## LLM Integration

### Configuration

LLM settings are read from `~/.env`:

```bash
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://your-api-endpoint
LLM_MODEL=qwen-coder-plus
```

### Client Implementation

```python
class LLMClient:
    """OpenAI-compatible LLM client with retry logic."""
    
    def chat(self, messages: List[ChatMessage], temperature: float = 0.3) -> str:
        """Send chat messages with retry on failure."""
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[m.to_dict() for m in messages],
                    temperature=temperature,
                )
                return response.choices[0].message.content
            except Exception as e:
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))
                else:
                    raise
```

## Report Generation

### Comprehensive Report Format

Each rule analysis includes:

1. **规则名称 (Rule Name)** - Chinese translation
2. **功能概述 (Description)** - 1-2 sentence summary
3. **关系代数表达式 (Relational Algebra)** - Using σ, π, ⋈, γ, τ
4. **输入模式 (Input Pattern)** - Operators, structure, triggers
5. **输出模式 (Output Pattern)** - Result operators and changes
6. **执行过程 (Execution Process)** - Step-by-step with mermaid flowchart
7. **优化收益 (Optimization Benefits)** - Data reduction, complexity, IO
8. **依赖条件 (Dependencies)** - Stats, cost, property requirements
9. **适用场景 (Applicable Scenarios)** - Best use cases
10. **SQL示例 (SQL Examples)** - Before/after optimization

## Testing Strategy

Tests follow TDD principles with pytest:

```python
def test_rule_miner_extract():
    """Test rule extraction from sample Java code."""
    miner = RuleMinerAgent(LLMClient(config))
    evidence = miner.analyze(context)
    
    assert len(evidence) > 0
    assert all(e.confidence > 0.5 for e in evidence)
```

## Error Handling

- SSL connection errors: Retry with exponential backoff
- LLM parsing failures: Fallback to basic analysis
- File encoding issues: Use utf-8 with error ignore
- Missing source directories: Skip with warning

## Performance Considerations

- LLM calls are expensive: Limit max_rules per engine (default: 30)
- Use ThreadPoolExecutor for parallel rule analysis
- Cache scanned rules to avoid re-scanning
- Progress reporting during long operations