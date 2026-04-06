"""Statistics and Cost extraction prompts for LLM-based analysis.

This module contains prompts used to extract statistics and cost model
information from source code using LLM analysis.
"""

STATS_EXTRACTION_PROMPT = """You are an expert in database query optimizer statistics systems.

Your task is to analyze source code and extract information about statistics
collection, storage, and usage in query optimization.

You should identify:
1. Statistics source (how stats are collected - ANALYZE command, automatic sampling)
2. Statistics objects (what stats are collected - NDV, row count, histograms, etc.)
3. Statistics granularity (table, column, partition, histogram levels)
4. Storage location (where stats are persisted - memory, disk, cache)
5. Collection triggers (what triggers stats collection - manual, auto, thresholds)
6. Collection scheduler (how collection is scheduled - periodic, on-demand)
7. Operator estimation logic (how stats are used for cardinality estimation)
8. Evidence from the code

Respond ONLY with valid JSON in the following format:
{{
    "stats_source": "Description of statistics collection source",
    "stats_objects": ["List of statistics objects collected"],
    "stats_granularity": "one of: table, column, partition, histogram",
    "storage_location": "Where statistics are stored (optional)",
    "collection_trigger": "What triggers statistics collection (optional)",
    "collection_scheduler": "How collection is scheduled (optional)",
    "operator_estimation_logic": "How stats are used for estimation (optional)",
    "uncertain_points": ["Points needing manual review"],
    "evidence": [
        {{
            "file_path": "path to source file",
            "description": "What this evidence demonstrates",
            "line_start": 10,
            "line_end": 20,
            "evidence_type": "one of: source_code, documentation, test, comment, config"
        }}
    ]
}}

If no valid statistics information can be extracted, respond with:
{{"error": "No statistics info found in the provided code", "reason": "explanation"}}

Be precise and reference specific code sections.

Engine: {engine}

Code:
```
{code}
```

Extract all relevant statistics information. Respond with ONLY valid JSON, no additional text."""

COST_EXTRACTION_PROMPT = """You are an expert in database query optimizer cost models.

Your task is to analyze source code and extract information about the cost
model used for query optimization decisions.

You should identify:
1. Cost formula location (where cost formulas are defined)
2. Cost dimensions (what factors are considered - CPU, I/O, memory, network)
3. Operator costs (cost formulas for specific operators - Scan, Join, Agg, etc.)
4. Evidence from the code

Respond ONLY with valid JSON in the following format:
{{
    "cost_formula_location": "Path or description of where formulas are defined",
    "cost_dimensions": ["List of cost dimensions considered"],
    "operator_costs": {{
        "OperatorName": "Cost formula or description"
    }},
    "uncertain_points": ["Points needing manual review"],
    "evidence": [
        {{
            "file_path": "path to source file",
            "description": "What this evidence demonstrates",
            "line_start": 10,
            "line_end": 20,
            "evidence_type": "one of: source_code, documentation, test, comment, config"
        }}
    ]
}}

If no valid cost model information can be extracted, respond with:
{{"error": "No cost info found in the provided code", "reason": "explanation"}}

Be precise and reference specific code sections.

Engine: {engine}

Code:
```
{code}
```

Extract all relevant cost model information. Respond with ONLY valid JSON, no additional text."""