# Optimizer Expert Analyzer Agent

A multi-engine query optimizer analysis system that performs deep analysis of database query optimizers across 8 different engines.

## Overview

This system analyzes query optimizers from 8 database engines:
- **StarRocks** (C++, Cascades)
- **Apache Doris** (Java, Cascades/Nereids)
- **ClickHouse** (C++, Custom multi-pass)
- **GPDB (Orca)** (C++, Cascades)
- **Apache Calcite** (Java, Volcano/HepPlanner)
- **CockroachDB** (Go, Optgen DSL + Cascades)
- **PostgreSQL** (C, Path-based)
- **Columbia** (C++, Academic Cascades)

## Architecture

The system follows a 3-task pipeline:

### Task 1: Enumeration
Language-aware file scanners extract rule definitions from source code:
- C++ class scanner (StarRocks, GPDB, Columbia)
- C++ function scanner (ClickHouse)
- Java AST scanner (Calcite, Doris)
- Optgen DSL scanner (CockroachDB)
- C function scanner (PostgreSQL)

### Task 2: Analysis
Harness loop analyzes each rule using LLM (Claude):
- RBO Rules (logical equivalence transformations)
- CBO Rules (physical implementation rules)
- Scalar Rules (expression rewriting)
- Property Rules (enforcer mechanisms)
- Statistics (cost model analysis)

### Task 3: Comparison
Multi-engine comparison:
- Canonical name normalization
- Diff matrix generation
- Alignment scoring
- Markdown report generation

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Step 1: Enumerate Rules

```bash
python run.py enumerate --engines starrocks calcite --source-root /path/to/source
```

This scans source code and generates `data/task_queue.json`.

### Step 2: Analyze Rules

```bash
export ANTHROPIC_API_KEY=your_key
python run.py analyze --engine starrocks
```

Results are saved to `data/{engine}/` as JSONL files.

### Step 3: Normalize Names

```bash
python run.py normalize
```

Normalizes rule names across engines for comparison.

### Step 4: Generate Comparison

```bash
python run.py compare
```

Generates diff matrix and scoring.

### Step 5: Generate Reports

```bash
python run.py report
```

Generates Markdown reports in `output/`.

### Run All Steps

```bash
python run.py runall --engines starrocks doris --source-root /path/to/source
```

## Project Structure

```
.
├── engines/              # Engine configuration YAML files
│   ├── starrocks.yaml
│   ├── doris.yaml
│   ├── clickhouse.yaml
│   ├── gpdb_orca.yaml
│   ├── calcite.yaml
│   ├── cockroachdb.yaml
│   ├── postgres.yaml
│   └── columbia.yaml
├── src/
│   ├── __init__.py
│   ├── models.py         # Data models and enums
│   ├── enumerator.py     # Rule enumeration logic
│   ├── harness.py        # LLM analysis harness
│   ├── comparison.py     # Cross-engine comparison
│   └── scanners/         # Language-specific scanners
│       ├── __init__.py
│       ├── base.py
│       ├── cpp_scanner.py
│       ├── java_scanner.py
│       ├── optgen_scanner.py
│       └── c_scanner.py
├── prompts/              # LLM prompt templates
│   ├── rbo_prompt.txt
│   ├── cbo_prompt.txt
│   ├── scalar_prompt.txt
│   └── property_prompt.txt
├── data/                 # Analysis output (JSONL)
├── output/               # Markdown reports
├── run.py                # Main CLI entry point
├── requirements.txt
└── DESIGN.md             # Full design document
```

## Configuration

Each engine has a YAML configuration file specifying:
- Language and optimizer framework
- Source file patterns (glob, class/function patterns)
- Key methods to extract
- Scanner hints

Example (`engines/starrocks.yaml`):
```yaml
engine_id: starrocks
language: cpp
optimizer_framework: cascades
optimizer_root: "./be/src/sql/optimizer"
patterns:
  rbo_rules:
    glob: "**/transform/rule_*.cpp"
    class_pattern: "class Rule\\w+\\s*:\\s*public TransformationRule"
    key_methods: ["transform", "check", "pattern"]
```

## Output Format

Each analyzed rule produces a JSON record:

```json
{
  "task_id": "starrocks::rbo::PushDownPredicates",
  "engine_id": "starrocks",
  "category": "rbo",
  "rule_name": "PushDownPredicates",
  "summary": "Pushes filter predicates down through join operators",
  "ra_input_pattern": "σ_p(R ⋈_q S)",
  "ra_output_pattern": "σ_p(R) ⋈_q S",
  "ra_condition": "p references only columns from R",
  "canonical_name": "predicate_pushdown.filter_through_join",
  "logical_category": "predicate_pushdown",
  "confidence": 0.92,
  "needs_review": false
}
```

## Design Document

See [DESIGN.md](DESIGN.md) for the complete design specification including:
- Architecture overview
- Data flow diagrams
- Prompt template designs
- Relational algebra symbol conventions
- Reliability mechanisms
- Implementation phases

## License

MIT License
