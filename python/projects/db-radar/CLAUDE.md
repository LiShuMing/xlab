You are my senior engineer mentor and code partner.

We will build a learning project on macOS using Python:
Project: Daily DB Radar
Goal:
- Learn agent development patterns (tools, memory, pipelines) using Anthropic + modern agent frameworks (LangChain optional).
- Improve daily work efficiency by collecting and summarizing DB/OLAP industry updates from a curated website list.

Inputs:
- A file named website.txt in the project root.
- website.txt contains lines describing competitor/product name and one or more URLs.
  Example line formats (we must support multiple):
  1) "DuckDB | https://duckdb.org/news/ | https://github.com/duckdb/duckdb/releases"
  2) "ClickHouse https://clickhouse.com/blog/ https://github.com/ClickHouse/ClickHouse/releases"
  3) "# comment" lines should be ignored
  4) blank lines ignored

Output:
- Each run generates one Markdown report in ./out/YYYY-MM-DD.md
- Also generates ./out/YYYY-MM-DD.json containing structured items and metadata.
- The report must cite sources as URLs and include brief extracted evidence (short snippets) per key claim.

Non-negotiables constraints:
1) Do not invent facts. Everything must be grounded in fetched content.
2) Every item must include: product name, source URL, publish date if available, and a short snippet.
3) If a page cannot be fetched or parsed, record it in the report under "Fetch Failures" with reason.
4) Keep the system extensible: new sources and new output formats can be added later.
5) Use English comments in code. Use clean, production-grade style. Avoid competitive-programming style.

Tech constraints:
- Python 3.11+
- Use Anthropic SDK (official) with ANTHROPIC_API_KEY and optionally ANTHROPIC_BASE_URL.
- Use requests/httpx + BeautifulSoup/readability-lxml for HTML extraction.
- Use feedparser for RSS/Atom when applicable.
- Use a simple local cache to avoid refetching unchanged pages:
  - store fetched content hash and ETag/Last-Modified if available in ./cache/
- Use a dedupe mechanism:
  - exact URL dedupe + similarity dedupe based on normalized title + domain + date.

Agent design requirements (important):
- Use a deterministic pipeline: Fetch -> Extract -> Normalize -> Rank -> Summarize -> Write.
- The LLM is used only for:
  a) classifying relevance to DB/OLAP systems and
  b) writing structured summaries and "why it matters".
- The LLM must NOT be used for web search. Only summarize what we fetched from the given sources.

Daily report format (Markdown):
1) Executive Summary (5 bullets max)
2) Top Updates (5-10 items)
   For each item:
   - [Product] Title
   - What changed (2-4 bullets)
   - Why it matters for OLAP / query engines (2 bullets)
   - Source(s): URLs
   - Evidence: 1-2 short snippets (<= 40 words each)
3) Release Notes Tracker (table by product)
4) Themes & Trends (3-6 bullets)
5) Action Items for Me (3-5 bullets; concrete follow-ups, e.g. "check feature X", "benchmark idea Y")
6) Fetch Failures

Ranking rules:
- Prefer official release notes, GitHub releases, engineering blogs, and docs updates.
- Prefer items within last 7 days by default; configurable.
- Prefer content about performance, execution engine, storage, query optimizer, governance, cost, serverless, lakehouse.

Configuration:
- CLI: python -m dbradar run --days 7 --max-items 80 --top-k 10
- Also support: python -m dbradar fetch --days 7
- Also support: python -m dbradar summarize --date YYYY-MM-DD

Deliverables for the first iteration (30 minutes MVP):
A) Project skeleton with modules:
   dbradar/
     __init__.py
     cli.py
     config.py
     sources.py
     fetcher.py
     extractor.py
     normalize.py
     ranker.py
     summarizer.py
     writer.py
     cache.py
   tests/ (optional for MVP)
B) A working run command that reads website.txt, fetches, extracts, calls Anthropic, writes Markdown.
C) Minimal caching and failure logging.

Implementation rules:
- Keep it simple and runnable first.
- Provide clear TODOs for later: vector memory, Slack/email delivery, trend comparisons, etc.
- Every module must be small and focused.

Start now:
- Propose the project skeleton, module responsibilities, and CLI.
- Implement the MVP code in one pass, ensuring it runs on macOS.
- Provide usage instructions and example website.txt format.
- Do not ask me questions; make reasonable assumptions and document them.

## Environment Constraints
- All Python commands must be executed within the pyenv environment: /Users/lishuming/work/xlab/python/pyenv-3.13.5
- Always prefix python commands with `pyenv exec` or ensure the virtualenv is active.
- Before running scripts, verify the environment using `python --version`.