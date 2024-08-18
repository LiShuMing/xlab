"""Property extraction prompts for LLM-based analysis.

This module contains prompts used to extract trait/property information from
source code using LLM analysis.
"""

PROPERTY_EXTRACTION_PROMPT = """You are an expert in database query optimizers and physical property enforcement.

Your task is to analyze source code and extract information about properties/traits used in the optimizer.
Properties are requirements that plans must satisfy (e.g., ordering, distribution, uniqueness).

You should identify:
1. Property name and type (logical or physical)
2. How the property is represented in code
3. How the property propagates through operators
4. Enforcer operators that can satisfy this property
5. Where this property is used in optimization

Respond ONLY with valid JSON in the following format:
{{
    "property_name": "name of the property (e.g., 'ordering', 'distribution', 'unique')",
    "property_type": "one of: logical, physical",
    "representation": "how property is represented in code (class name, data structure)",
    "propagation_logic": "how property propagates through operators (e.g., 'preserved by', 'destroyed by', 'required by')",
    "enforcer": "operator that enforces this property (e.g., 'Sort', 'HashAggregate')",
    "where_used": ["list of operators or rules that use this property"],
    "impact_on_search": "how this property affects search space (optional)",
    "evidence": [
        {{
            "file_path": "path to source file",
            "description": "What this evidence demonstrates",
            "line_start": 10,
            "line_end": 20,
            "evidence_type": "one of: source_code, documentation, test, comment, config"
        }}
    ],
    "confidence": "one of: high, medium, low, unknown",
    "uncertain_points": ["Points needing manual review"]
}}

If no valid property can be extracted from the code, respond with:
{{"error": "No property found in the provided code", "reason": "explanation"}}

Be precise and reference specific code sections. Set confidence based on how certain you are about the analysis.

Engine: {engine}
Property directory context: {context}

Code:
```
{code}
```

Extract all relevant information about any property/trait in this code.
Focus on identifying the property's role in the optimization process.
Respond with ONLY valid JSON, no additional text."""

PROPERTY_SYSTEM_PROMPT = """You are an expert in database query optimizers and property enforcement theory.

Properties (also called traits) are requirements that execution plans must satisfy:
- Logical properties: derived from the plan itself (e.g., output schema, cardinality estimates)
- Physical properties: requirements imposed by the optimization process (e.g., ordering, distribution)

Enforcer operators are operators that can satisfy a property requirement:
- Sort enforces ordering property
- Exchange/Shuffle enforces distribution property
- HashAggregate can enforce uniqueness property

When analyzing code, identify:
1. Property definitions and representations
2. Property propagation rules (how properties flow through operators)
3. Enforcer logic (when and how to add enforcers)
4. Property requirements in optimization rules

Be precise and provide evidence from the code."""

PROPERTY_ANALYSIS_PROMPT = """Analyze the following property-related code from a query optimizer.

Engine: {engine}

Code:
```
{code}
```

Provide a comprehensive analysis of:
1. What property is being defined or used
2. The property's type and representation
3. Propagation logic for this property
4. Enforcer operators for this property
5. Impact on the optimization search space

Respond with ONLY valid JSON following the property extraction schema."""