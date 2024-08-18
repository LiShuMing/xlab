"""Prompt templates for LLM analysis."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pia.models.product import Product
    from pia.models.release import Release
    from pia.models.source_doc import NormalizedDoc
    from pia.llm.schemas import ReleaseExtraction

SYSTEM_PROMPT = """You are a senior analyst specializing in databases and big data systems.
You have deep knowledge of OLAP, data warehouses, lake-houses, and stream processing.

Your analysis is:
- Precise: distinguish between features, architecture signals, and commercial signals
- Honest: don't inflate patch releases into strategic pivots
- Evidence-based: ground every claim in the release notes
- Comparative: consider competitive context when relevant
- Structured: always output the requested format exactly

When you encounter a patch release, say so clearly. Not every release is a strategic event.
Always distinguish between "explicitly stated" and "inferred"."""


def make_extraction_prompt(
    product_name: str,
    version: str,
    content: str,
) -> str:
    """Build the Stage A extraction prompt.

    Asks the model to extract structured facts from release notes into a
    JSON object matching the ReleaseExtraction schema.

    Args:
        product_name: Human-readable product name.
        version: Release version string.
        content: Normalized markdown content of the release notes.

    Returns:
        Formatted prompt string.
    """
    # Truncate very long content to avoid token limits
    MAX_CONTENT_CHARS = 40000
    if len(content) > MAX_CONTENT_CHARS:
        content = content[:MAX_CONTENT_CHARS] + "\n\n[... content truncated ...]"

    return f"""## Task: Structured Extraction from Release Notes

Product: **{product_name}**
Version: **{version}**

### Release Notes:
{content}

---

## Instructions

Analyze the release notes above and extract the following information as a JSON object.
Return ONLY valid JSON inside a ```json ... ``` code block.

```json
{{
  "version": "{version}",
  "core_features": ["list of significant new features or capabilities added"],
  "breaking_changes": ["list of breaking changes, migration requirements, deprecated items"],
  "categories": {{
    "performance": ["performance improvements, query optimization, indexing"],
    "storage": ["storage engine changes, compression, formats"],
    "sql": ["SQL dialect changes, new functions, operators"],
    "connectors": ["data source connectors, integrations, external table support"],
    "ai_ml": ["AI/ML features, vector search, model serving"],
    "security": ["auth, encryption, access control changes"],
    "cloud": ["cloud-native features, managed service changes"],
    "observability": ["monitoring, metrics, tracing, profiling"],
    "operations": ["deployment, configuration, upgrade process"],
    "other": ["anything that doesn't fit the above categories"]
  }},
  "target_audience": ["data_engineer", "database_engineer", "data_scientist", "platform_engineer", "pm"],
  "release_type": "patch | minor | major",
  "inferred_direction": ["inferences about product strategy based on this release, marked as INFERRED"]
}}
```

Rules:
1. Only include categories that have actual content.
2. Be conservative about release_type: most releases are "patch" or "minor".
3. Mark any inference in inferred_direction with [INFERRED] prefix.
4. Keep each list item concise (one sentence max).
5. If breaking_changes is empty, use an empty list [].
"""


def make_analysis_prompt(
    product: "Product",
    release: "Release",
    extraction: "ReleaseExtraction",
    normalized_doc: "NormalizedDoc",
    supplemental: list[str] | None = None,
) -> str:
    """Build the Stage B analysis prompt.

    Generates a comprehensive expert analysis report using the structured
    extraction from Stage A as its primary input.

    Args:
        product: Product configuration with analysis settings.
        release: Release metadata.
        extraction: Structured extraction from Stage A.
        normalized_doc: Normalized source document.
        supplemental: Optional list of supplemental markdown content.

    Returns:
        Formatted prompt string.
    """
    competitor_list = ", ".join(product.analysis.competitor_set) if product.analysis.competitor_set else "N/A"
    audience_list = ", ".join(product.analysis.audience) if product.analysis.audience else "general technical audience"

    extraction_json = extraction.model_dump_json(indent=2)

    # Format categories for readability
    categories_text = ""
    for cat, items in extraction.categories.items():
        if items:
            categories_text += f"\n**{cat.title()}:**\n"
            for item in items:
                categories_text += f"  - {item}\n"

    supplemental_text = ""
    if supplemental:
        supplemental_text = "\n### Supplemental Sources:\n"
        for i, s in enumerate(supplemental[:3], 1):
            supplemental_text += f"\n**Source {i}:**\n{s[:3000]}\n"

    published = release.published_at.strftime("%Y-%m-%d") if release.published_at else "unknown"

    return f"""## Task: Expert Analysis Report

### Product Profile
- **Product**: {product.name}
- **Category**: {product.category}
- **Homepage**: {product.homepage}
- **Description**: {product.description}
- **Prompt Profile**: {product.analysis.prompt_profile}

### Release Information
- **Version**: {release.version}
- **Published**: {published}
- **Source**: {release.source_url}
- **Release Type**: {extraction.release_type}

### Structured Extraction (Stage A output)

**Core Features:**
{chr(10).join(f"- {f}" for f in extraction.core_features) if extraction.core_features else "- None identified"}

**Breaking Changes:**
{chr(10).join(f"- {c}" for c in extraction.breaking_changes) if extraction.breaking_changes else "- None"}

**By Category:**
{categories_text or "No category breakdown available."}

**Inferred Direction:**
{chr(10).join(f"- {d}" for d in extraction.inferred_direction) if extraction.inferred_direction else "- No strong signals"}

### Analysis Context
- **Primary Competitors to reference**: {competitor_list}
- **Target Audience for this report**: {audience_list}
{supplemental_text}

---

## Instructions

Write a comprehensive analysis report in markdown format following the structure below.
Be precise and evidence-based. Distinguish between explicit release content and inference.
If this is a patch release, say so and keep the strategic analysis proportional.

Use exactly these section headers:

# {product.name} {release.version} — Release Analysis

## TL;DR
[2-4 sentences: what is this release and why does it matter? Be honest if it's a minor patch.]

## What Changed
[Organized breakdown of changes. Use the category structure from the extraction. Include specific feature names and technical details. Use subheadings for major categories.]

## Why It Matters
[Technical significance. What problems does this solve? What enables these changes?]

## Product Direction
[What does this release signal about where the product is heading? What themes are emerging over time? Always label inferences clearly with "(inferred)".]

## Impact on Users

### For Data Engineers
[Concrete impact: what changes for them, what do they need to do?]

### For Database Engineers / DBAs
[Concrete impact on operations, tuning, migration.]

### For Platform Engineers / PMs
[Strategic considerations, planning implications.]

## Competitive View
[How does this compare to {competitor_list}? Are they catching up, pulling ahead, or moving in a different direction? Be specific, not generic.]

## Caveats & Limitations
[What's missing? What should users watch out for? Any known issues? Any features that sound bigger than they are?]

## Evidence & Links
[List key source URLs, GitHub issues, PR links, or doc links referenced in the release notes.]

---

Write the full report now. Do not add commentary outside the report structure.
"""


def make_digest_prompt(
    products_info: list[dict[str, Any]],
    time_window: str,
) -> str:
    """Build the multi-product digest prompt.

    Args:
        products_info: List of dicts with 'product', 'releases', 'latest_summary' keys.
        time_window: Time window label (e.g. 'weekly', 'monthly').

    Returns:
        Formatted prompt string.
    """
    products_text = ""
    for info in products_info:
        product = info["product"]
        releases = info.get("releases", [])
        summary = info.get("latest_summary", "No analysis available.")

        versions = [r.version for r in releases[:5]]
        products_text += f"""
### {product.name}
- **New versions**: {', '.join(versions) if versions else 'No new releases'}
- **Category**: {product.category}
- **Summary of latest**: {summary[:1500]}
"""

    window_label = time_window.capitalize()

    return f"""## Task: {window_label} Product Intelligence Digest

### Time Window: {time_window}

### Products Covered:
{products_text}

---

## Instructions

Write a {time_window} digest report covering the above products.
Format as markdown. Be analytical, not just descriptive.

Use this structure:

# {window_label} Big Data / Database Intelligence Digest

## Executive Summary
[3-5 bullet points: the most important things that happened this week/month]

## Product Updates

[For each product with updates, write a short section:]
### [Product Name]
- Key releases and what's notable
- Any strategic signals

## Cross-Product Themes
[What patterns are you seeing across products? What are multiple vendors all working on? Where are the competitive battles?]

## Industry Signals
[What do these releases collectively tell us about the direction of the data infrastructure market?]

## What to Watch Next
[Upcoming developments, things to monitor, products to keep an eye on]

---

Write the full digest now.
"""
