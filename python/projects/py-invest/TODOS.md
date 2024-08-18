# TODO List - py-invest

## High Priority

### 1. Add LLM Rate Limiting and Cost Control
**What:** Add rate limiting, token tracking, and budget caps to LLM calls.
**Why:** 5 LLM calls per analysis with no limits. Could hit API limits silently.
**Context:** Each specialist makes 3000+ char prompts. One burst could exhaust quota.
**Created:** 2026-03-23
**Status:** Open

### 2. Migrate Data Collectors to HTTPS
**What:** Change all Sina API calls from HTTP to HTTPS.
**Why:** HTTP allows MITM attacks to inject fake price data.
**Context:** price_collector.py uses `http://hq.sinajs.cn/`
**Depends on:** Verifying Sina supports HTTPS
**Created:** 2026-03-23
**Status:** Open

### 3. Create Test Suite
**What:** Create tests/ directory with unit tests for all modules.
**Why:** 0% test coverage. No regression protection.
**Context:** Test files needed:
- test_specialist_agents.py
- test_tools.py
- test_formatter.py
- test_cli.py
**Created:** 2026-03-23
**Status:** In Progress (included in eng review fixes)

---

## From Engineering Review (2026-03-23)

### Fixes Accepted (to implement)

1. **DRY Violation in Tools** - Use `self._collector` instead of creating new instances in execute()
2. **Hardcoded Chinese in Synthesis** - Make language dynamic based on `--en` flag
3. **Duplicated Helper Functions** - Extract to `agents/utils.py`
4. **Silent Tool Failures** - Add error context in orchestrator
5. **Dead Code Removal** - Remove `apps/web/`, `apps/api/`, `storage/`
6. **Silent Exception Handling** - Add logging in specialist agents
7. **HTTP Session Reuse** - Reuse aiohttp session in collectors
8. **Fake Data Issue** - Remove or clearly mark fake news data
9. **Async Blocking** - Replace `invoke()` with `ainvoke()` in fallback paths
10. **Missing Report Section** - Add bull/base/bear section to sections list

### Critical Gaps Flagged

1. **Fake data returned as real** - news_collector.py returns fabricated data
2. **Sync LLM blocks event loop** - specialist_agents.py uses `invoke()` in async
3. **Missing report section** - synthesis_agent.py skips order=3 section
4. **Zero test coverage** - No tests exist