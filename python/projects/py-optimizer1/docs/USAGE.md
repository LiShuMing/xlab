# Optimizer Expert Analyzer - Usage Documentation

## Quick Start

### 1. Environment Setup

```bash
# Use the specified Python environment
source /home/lism/.venv/general-3.12/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. LLM Configuration

Create/edit `~/.env` file:

```bash
# LLM Configuration (Qwen OpenAI-compatible API)
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-coder-plus
```

### 3. Source Code Paths

Ensure optimizer source code is available:

```
StarRocks: /home/lism/work/starrocks
Calcite:   /home/lism/work/calcite
Doris:     /home/lism/work/doris
```

## Running Analysis

### Generate Comprehensive Reports

```bash
# Analyze all engines
python generate_comprehensive_reports.py --engines StarRocks Calcite Doris

# Analyze specific engine
python generate_comprehensive_reports.py --engines StarRocks

# Adjust max rules per engine
python generate_comprehensive_reports.py --engines StarRocks --max-rules 50

# Custom output directory
python generate_comprehensive_reports.py --engines StarRocks --output ./my_reports
```

### Generate Detailed Reports (without LLM)

```bash
# Faster analysis without LLM semantic analysis
python generate_detailed_reports.py
```

### Run Full Analysis Pipeline

```bash
# Complete analysis with comparison
python run_analysis.py
```

## Output Files

### Comprehensive Reports

```
analysis_output/comprehensive_reports/
├── starrocks_规则深度分析.md   # StarRocks deep analysis
├── calcite_规则深度分析.md     # Calcite deep analysis
├── doris_规则深度分析.md       # Doris deep analysis
```

### Detailed Reports (Relational Algebra)

```
analysis_output/detailed_reports/
├── starrocks_优化规则详细分析.md
├── calcite_优化规则详细分析.md
├── doris_优化规则详细分析.md
```

### Comparison Reports

```
analysis_output/
├── OPTIMIZER_COMPARISON_REPORT.md  # Cross-engine comparison
```

## Report Content

Each comprehensive report includes:

### Rule Overview

- Rule categories and counts
- Analysis completion percentage

### Relational Algebra Symbols

| Symbol | Meaning |
|--------|---------|
| σ | Selection (filter) |
| π | Projection |
| ⋈ | Join |
| γ | Aggregation |
| τ | Sort |

### Per-Rule Analysis

1. **Input Pattern** - What operators the rule matches
2. **Output Pattern** - How the rule transforms operators
3. **Execution Process** - Step-by-step transformation logic
4. **Optimization Benefits** - Performance improvements
5. **Dependencies** - Required conditions (stats/cost/property)
6. **SQL Examples** - Before/After query plans

## Programmatic Usage

### Using the Analyzer Directly

```python
from optimizer_analysis.llm_client import LLMClient
from optimizer_analysis.config import LLMConfig
from optimizer_analysis.engines.presets import STARROCKS_CONFIG
from generate_comprehensive_reports import DetailedRuleAnalyzer

# Initialize LLM client
config = LLMConfig.from_env_file()
client = LLMClient(config)
analyzer = DetailedRuleAnalyzer(client)

# Analyze a specific rule
analysis = analyzer.analyze_rule_comprehensive(
    class_name="PushDownLimitJoinRule",
    code="...",  # Java source code
    filename="PushDownLimitJoinRule.java"
)

print(analysis["rule_name_cn"])
print(analysis["relational_algebra"])
```

### Scanning Rules

```python
from optimizer_analysis.scanners.java_scanner import JavaScanner

scanner = JavaScanner()
code = java_file.read_text()
classes = scanner.extract_classes(code)
```

### Engine Registry

```python
from optimizer_analysis.engines.registry import EngineRegistry
from optimizer_analysis.engines.presets import STARROCKS_CONFIG

registry = EngineRegistry()
registry.register(STARROCKS_CONFIG)

# Get engine by name
engine = registry.get("StarRocks")
print(engine.optimizer_style)  # 'cascades'
```

## Configuration Options

### generate_comprehensive_reports.py

| Argument | Default | Description |
|----------|---------|-------------|
| `--engines` | StarRocks | Engines to analyze |
| `--output` | ./analysis_output/comprehensive_reports | Output directory |
| `--max-rules` | 30 | Max rules per engine for LLM analysis |

### LLMConfig

| Field | Source | Description |
|-------|--------|-------------|
| `api_key` | LLM_API_KEY | API authentication key |
| `base_url` | LLM_BASE_URL | API endpoint URL |
| `model` | LLM_MODEL | Model name (default: qwen-coder-plus) |

## Best Practices

### For LLM Analysis

1. **Limit rules** - Use `--max-rules` to control API costs
2. **Check API status** - Verify LLM endpoint availability before running
3. **Monitor progress** - Watch console output for analysis status

### For Source Code

1. **Ensure paths exist** - Verify source directories before analysis
2. **Exclude tests** - Test files are automatically skipped
3. **Handle encoding** - UTF-8 encoding used with error tolerance

### For Reports

1. **Chinese format** - Reports generated in Chinese for readability
2. **Mermaid diagrams** - Execution process includes flowcharts
3. **Cross-engine comparison** - Use comparison report for overview

## Troubleshooting

### LLM Connection Errors

```
Error: SSL connection failed
Solution: Check LLM_BASE_URL and API endpoint availability
```

### Missing Source Code

```
Error: 源码不存在: /path/to/engine
Solution: Verify source directory exists or update paths in ENGINE_PATHS
```

### Encoding Errors

```
Error: UnicodeDecodeError
Solution: Scanner uses utf-8 with errors='ignore' for tolerance
```

### Low Analysis Confidence

```
Warning: Analysis confidence < 0.5
Solution: Rule may need manual review; LLM may not have enough context
```

## Requirements Compliance

Following ~/.RULES.md:

1. ✓ Uses `/home/lism/.venv/general-3.12` environment
2. ✓ LLM configuration from `~/.env` (LLM_xxx)
3. ✓ Python strong typing with Pydantic schemas
4. ✓ Interface-first architecture (BaseAgent abstract)
5. ✓ Changes logged to CHANGES_LOG.md
6. ✓ Task decomposition for large tasks (Phase 1-3 plans)