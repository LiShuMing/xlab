
Implement a Python CLI application named `pia` (Product Intelligence Agent).

Goal:
Build an MVP CLI tool that tracks official release notes / changelogs for database and big-data products, normalizes the source content, analyzes a selected release with an LLM, and persists the generated report to avoid duplicate analysis.

Requirements:
1. Use Python 3.11+.
2. Use Typer for CLI.
3. Use Pydantic for data models.
4. Use SQLite for metadata persistence.
5. Use YAML files under `products/` to define product source configs.
6. Support these commands:
   - `pia product list`
   - `pia sync <product>`
   - `pia versions <product>`
   - `pia analyze latest <product>`
   - `pia analyze version <product> <version>`
7. Implement source adapters:
   - GitHub releases adapter
   - Generic docs HTML adapter
8. Save:
   - raw fetched pages
   - normalized markdown snapshots
   - generated reports
9. Use a provider abstraction for LLM calls so models/providers can be swapped later.
10. Implement report caching keyed by:
   `(product_id, version, report_type, model_name, prompt_version, normalized_hash)`

Output format for analysis reports:
- TL;DR
- What changed
- Why it matters
- Product direction inference
- Impact on users
- Competitive view
- Caveats
- Evidence links

Code quality requirements:
- clear module boundaries
- typed code
- docstrings for public APIs
- basic tests for parsing, version normalization, and caching
- no web UI
- keep MVP simple and extensible
