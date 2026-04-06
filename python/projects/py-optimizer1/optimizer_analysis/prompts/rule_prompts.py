"""Rule extraction prompts for LLM-based analysis.

This module contains prompts used to extract optimization rules from
source code using LLM analysis.
"""

RULE_EXTRACTION_SYSTEM_PROMPT = """You are an expert in database query optimizers and rule-based query optimization.

Your task is to analyze source code and extract information about optimization rules.
You should identify:
1. Rule identification (name, ID, category)
2. When the rule fires (lifecycle stage, trigger patterns)
3. What the rule transforms (input/output operators, transformation logic)
4. Dependencies (statistics, cost model, physical properties)
5. Evidence from the code

Respond ONLY with valid JSON in the following format:
{
    "rule_id": "unique identifier (e.g., R001, C001)",
    "rule_name": "Human-readable rule name",
    "rule_category": "one of: rbo, cbo, scalar, post_opt, implicit",
    "implementation_type": "one of: explicitly_implemented, implicitly_implemented, framework_provided, not_applicable",
    "lifecycle_stage": "When this rule fires (e.g., 'logical_optimization', 'physical_optimization')",
    "source_files": ["list of source files implementing this rule"],
    "registration_points": ["where the rule is registered"],
    "trigger_pattern": "Pattern that triggers this rule (optional)",
    "preconditions": ["Preconditions for rule application"],
    "transformation_logic": "What the rule transforms",
    "input_operators": ["Input operator types"],
    "output_operators": ["Output operator types"],
    "relational_algebra_form": "Relational algebra expression if applicable",
    "depends_on_stats": false,
    "depends_on_cost": false,
    "depends_on_property": false,
    "examples": ["Example transformations"],
    "confidence": "one of: high, medium, low, unknown",
    "uncertain_points": ["Points needing manual review"],
    "evidence": [
        {
            "file_path": "path to source file",
            "description": "What this evidence demonstrates",
            "line_start": 10,
            "line_end": 20,
            "evidence_type": "one of: source_code, documentation, test, comment, config"
        }
    ]
}

If no valid rule can be extracted from the code, respond with:
{"error": "No rule found in the provided code", "reason": "explanation"}

Be precise and reference specific code sections. Set confidence based on how certain you are about the analysis."""

RULE_EXTRACTION_USER_PROMPT = """Analyze the following code and extract optimization rule information.

Engine: {engine}
Rule Category: {category}

Code:
```
{code}
```

Extract all relevant information about any optimization rule(s) in this code.
If multiple rules are found, focus on the most prominent one or describe the primary rule pattern.
Respond with ONLY valid JSON, no additional text."""

RBO_RULE_PROMPT = """You are analyzing a Rule-Based Optimization (RBO) rule.

RBO rules are characterized by:
- Pattern-based transformation logic that applies heuristics
- No dependency on cost models or statistics
- Usually applied in a fixed order or based on pattern matching
- Examples: predicate pushdown, projection pruning, join reordering heuristics

Engine: {engine}
Rule Category: RBO (Rule-Based Optimization)

Code:
```
{code}
```

Focus on identifying:
1. The pattern this rule matches (e.g., specific operator tree structure)
2. The transformation applied when the pattern matches
3. Any preconditions or guard conditions
4. The expected benefit (why this transformation is beneficial)

Respond with ONLY valid JSON following the rule extraction schema."""

CBO_RULE_PROMPT = """You are analyzing a Cost-Based Optimization (CBO) rule.

CBO rules are characterized by:
- Dependencies on cost model estimates
- Use of statistics (table statistics, column statistics, histograms)
- Cost-based decision making between alternative plans
- Examples: join order optimization, index selection, access path selection

Engine: {engine}
Rule Category: CBO (Cost-Based Optimization)

Code:
```
{code}
```

Focus on identifying:
1. What statistics or cost information this rule uses
2. The cost-based decision logic
3. Alternative plans being compared
4. How the rule chooses the best plan

Respond with ONLY valid JSON following the rule extraction schema."""