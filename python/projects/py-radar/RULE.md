# Harness Engineering Rules for AI Agent Development

This document defines engineering standards and best practices for AI Agent development in this project, inspired by OpenAI's Harness Engineering principles.

## 1. Structured Output Validation

### Rule 1.1: Use Pydantic for LLM Output Validation
- **Requirement**: All LLM outputs MUST be validated using Pydantic models
- **Rationale**: Prevents runtime errors from malformed JSON and provides clear error messages
- **Implementation**:
  ```python
  from pydantic import BaseModel, Field

  class SummaryOutput(BaseModel):
      executive_summary: list[str] = Field(..., min_length=1)
      themes: list[str] = Field(default_factory=list)
      action_items: list[str] = Field(default_factory=list)
  ```

### Rule 1.2: Implement JSON Repair Fallback
- **Requirement**: When LLM returns invalid JSON, attempt repair before failing
- **Rationale**: LLM outputs may contain markdown wrappers or minor formatting issues
- **Implementation**: Use `instructor` library or custom repair logic with retry

## 2. Observability & Telemetry

### Rule 2.1: Structured Logging Only
- **Requirement**: Never use `print()`. Use `structlog` for all logging
- **Rationale**: Enables log aggregation, filtering, and analysis
- **Implementation**:
  ```python
  import structlog
  logger = structlog.get_logger()
  logger.info("agent_action", action="summarize", item_count=len(items))
  ```

### Rule 2.2: LLM I/O Tracing
- **Requirement**: Log complete LLM request/response at DEBUG level
- **Rationale**: Essential for debugging hallucinations and API issues
- **Implementation**:
  ```python
  logger.debug("llm_request", payload=payload, correlation_id=correlation_id)
  logger.debug("llm_response", response=response, latency_ms=latency)
  ```

### Rule 2.3: Context Propagation
- **Requirement**: Use `contextvars` to propagate request context across async boundaries
- **Rationale**: Enables distributed tracing and correlation of logs
- **Implementation**:
  ```python
  from contextvars import ContextVar
  correlation_id = ContextVar("correlation_id", default=None)
  ```

## 3. Error Handling & Resilience

### Rule 3.1: Smart Retry with Exponential Backoff
- **Requirement**: Use `tenacity` for LLM API calls with exponential backoff
- **Rationale**: Handles transient failures without overwhelming the API
- **Implementation**:
  ```python
  from tenacity import retry, stop_after_attempt, wait_exponential

  @retry(
      stop=stop_after_attempt(3),
      wait=wait_exponential(multiplier=1, min=4, max=60),
      retry=retry_if_exception_type((TimeoutError, NetworkError))
  )
  def call_llm(payload: dict) -> dict:
      ...
  ```

### Rule 3.2: Graceful Degradation
- **Requirement**: When LLM calls fail, return partial results or cached data
- **Rationale**: System should remain functional even with LLM outages
- **Implementation**: Always have a fallback path for critical operations

### Rule 3.3: Circuit Breaker Pattern
- **Requirement**: Implement circuit breaker for external API calls
- **Rationale**: Prevents cascade failures when external service is down
- **Implementation**: Use `pybreaker` or custom implementation

## 4. Prompt Engineering

### Rule 4.1: External Prompt Management
- **Requirement**: Store prompts in external files, not hardcoded strings
- **Rationale**: Enables version control, A/B testing, and hot-reloading
- **Implementation**:
  ```
  dbradar/prompts/
  ├── summary_v1.txt
  ├── summary_v2.txt
  └── registry.yaml
  ```

### Rule 4.2: Prompt Version Tracking
- **Requirement**: Include prompt version in LLM request metadata
- **Rationale**: Enables tracing output quality to prompt version
- **Implementation**: Add `prompt_version` field to all LLM calls

## 5. Testing & Evaluation

### Rule 5.1: Deterministic Evaluation Dataset
- **Requirement**: Maintain a curated dataset for evaluating LLM outputs
- **Rationale**: Quantifies output quality changes over time
- **Implementation**: Store test fixtures in `tests/evaluation/fixtures/`

### Rule 5.2: Automated Quality Metrics
- **Requirement**: Implement automated metrics for LLM output quality
- **Rationale**: Catches regressions in CI/CD pipeline
- **Metrics**:
  - Structured output validity rate
  - Fact consistency score
  - Hallucination detection rate

### Rule 5.3: Shadow Mode Testing
- **Requirement**: Run new prompt versions in shadow mode before rollout
- **Rationale**: Compare outputs without affecting production
- **Implementation**: Log shadow outputs for offline comparison

## 6. Performance & Resource Management

### Rule 6.1: Connection Pooling
- **Requirement**: Use `httpx.AsyncClient` with connection limits
- **Rationale**: Prevents resource exhaustion under high load
- **Implementation**:
  ```python
  limits = httpx.Limits(max_connections=20, max_keepalive_connections=10)
  client = httpx.AsyncClient(limits=limits)
  ```

### Rule 6.2: Concurrency Limits
- **Requirement**: Use semaphore to limit concurrent LLM requests
- **Rationale**: Prevents rate limiting and resource contention
- **Implementation**:
  ```python
  semaphore = asyncio.Semaphore(max_concurrent)
  ```

### Rule 6.3: Multi-Level Caching
- **Requirement**: Implement L1 (memory), L2 (disk), L3 (semantic) caching
- **Rationale**: Reduces LLM API costs and improves latency
- **Implementation**:
  - L1: `functools.lru_cache` or `cachetools`
  - L2: Disk cache with `diskcache`
  - L3: Vector similarity with `sentence-transformers`

## 7. Configuration Management

### Rule 7.1: Type-Safe Configuration
- **Requirement**: Use Pydantic Settings for all configuration
- **Rationale**: Validates config at startup, prevents runtime errors
- **Implementation**:
  ```python
  from pydantic_settings import BaseSettings

  class Settings(BaseSettings):
      llm_api_key: SecretStr
      llm_timeout: int = 300
  ```

### Rule 7.2: Dependency Injection
- **Requirement**: Pass dependencies explicitly, avoid global state
- **Rationale**: Improves testability and modularity
- **Implementation**:
  ```python
  class Agent:
      def __init__(self, settings: Settings | None = None):
          self.settings = settings or Settings()
  ```

## 8. Documentation Requirements

### Rule 8.1: CHANGE_LOGS.md Updates
- **Requirement**: Every code change MUST be documented in CHANGE_LOGS.md
- **Format**: Follow existing format with date, description, and technical details
- **Timing**: Update BEFORE committing changes

### Rule 8.2: Design Decision Records
- **Requirement**: Document significant architectural decisions in `docs/adr/`
- **Rationale**: Preserves context for future developers
- **Format**: Use ADR template with context, decision, consequences

## Compliance Checklist

Before committing code changes, verify:

- [ ] All LLM outputs use Pydantic validation
- [ ] Structured logging is used (no print statements)
- [ ] Retry logic is implemented for external API calls
- [ ] Graceful degradation is handled
- [ ] Changes are documented in CHANGE_LOGS.md
- [ ] Tests pass including evaluation tests
- [ ] Configuration uses Pydantic Settings

## References

- [OpenAI Harness Engineering](https://openai.com/index/harness-engineering/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Structlog Documentation](https://www.structlog.org/)
- [Tenacity Documentation](https://github.com/jd/tenacity)
