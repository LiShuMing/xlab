"""M3.2: Online serving load generator with Poisson arrivals and SLO Goodput metrics.

Generates deterministic seeded Poisson arrival traces (`inter_arrival ~ Exp(qps)`) with
mixed short/long prompt & output lengths, and evaluates serving quality under explicit
TTFT + TPOT SLOs:
  - TTFT (Time To First Token): P50 / P95 / P99
  - TPOT (Time Per Output Token) & ITL (Inter-Token Latency): P50 / P95 / P99
  - Throughput (output tokens/s) vs Goodput (requests/s & % meeting BOTH TTFT and TPOT SLOs)

Supports both OpenAI-compatible SSE endpoints (`run_http_load`) and pluggable async
callables (`run_load`) for deterministic testing and local engine evaluation.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
import json
import random
import statistics
import time
from typing import Any, Awaitable, Callable

import httpx


@dataclass(frozen=True)
class LoadRequestSpec:
    req_id: int
    arrival_offset_s: float
    prompt_tokens: int
    output_tokens: int
    prompt_text: str


@dataclass(frozen=True)
class RequestObservation:
    req_id: int
    prompt_tokens: int
    output_tokens: int
    ttft_ms: float
    tpot_ms: float
    e2e_ms: float
    itl_ms: list[float]
    ok: bool = True
    error: str | None = None


@dataclass(frozen=True)
class ServingSummary:
    num_requests: int
    num_ok: int
    qps_target: float
    wall_s: float
    achieved_rps: float
    output_tok_per_s: float
    ttft_p50_ms: float
    ttft_p95_ms: float
    ttft_p99_ms: float
    tpot_p50_ms: float
    tpot_p95_ms: float
    tpot_p99_ms: float
    itl_p99_ms: float
    ttft_slo_ms: float
    tpot_slo_ms: float
    goodput_ratio: float
    goodput_rps: float


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(p * (len(ordered) - 1)))
    return ordered[idx]


def generate_poisson_workload(
    num_requests: int,
    qps: float,
    *,
    seed: int = 42,
    short_ratio: float = 0.75,
    short_prompt_range: tuple[int, int] = (32, 128),
    long_prompt_range: tuple[int, int] = (384, 768),
    output_range: tuple[int, int] = (16, 64),
) -> list[LoadRequestSpec]:
    """Generate a reproducible Poisson arrival sequence with mixed short/long prompts."""
    if num_requests <= 0 or qps <= 0:
        raise ValueError("num_requests and qps must be positive.")
    rng = random.Random(seed)
    t = 0.0
    specs: list[LoadRequestSpec] = []
    for req_id in range(num_requests):
        if req_id > 0:
            t += rng.expovariate(qps)
        if rng.random() < short_ratio:
            p_len = rng.randint(*short_prompt_range)
        else:
            p_len = rng.randint(*long_prompt_range)
        out_len = rng.randint(*output_range)
        prompt_text = " ".join(f"tok{rng.randint(0, 999)}" for _ in range(p_len))
        specs.append(
            LoadRequestSpec(
                req_id=req_id,
                arrival_offset_s=round(t, 6),
                prompt_tokens=p_len,
                output_tokens=out_len,
                prompt_text=prompt_text,
            )
        )
    return specs


def summarize_observations(
    observations: list[RequestObservation],
    *,
    qps_target: float,
    wall_s: float,
    ttft_slo_ms: float = 500.0,
    tpot_slo_ms: float = 50.0,
) -> ServingSummary:
    """Aggregate raw request traces into TTFT/TPOT/ITL percentiles and SLO Goodput."""
    ok_obs = [o for o in observations if o.ok]
    ttfts = [o.ttft_ms for o in ok_obs]
    tpots = [o.tpot_ms for o in ok_obs]
    all_itls = [v for o in ok_obs for v in o.itl_ms]
    total_out_tokens = sum(o.output_tokens for o in ok_obs)
    good_count = sum(1 for o in ok_obs if o.ttft_ms <= ttft_slo_ms and o.tpot_ms <= tpot_slo_ms)
    denom = max(wall_s, 1e-6)
    return ServingSummary(
        num_requests=len(observations),
        num_ok=len(ok_obs),
        qps_target=qps_target,
        wall_s=round(wall_s, 4),
        achieved_rps=round(len(ok_obs) / denom, 2),
        output_tok_per_s=round(total_out_tokens / denom, 1),
        ttft_p50_ms=round(percentile(ttfts, 0.50), 2),
        ttft_p95_ms=round(percentile(ttfts, 0.95), 2),
        ttft_p99_ms=round(percentile(ttfts, 0.99), 2),
        tpot_p50_ms=round(percentile(tpots, 0.50), 2),
        tpot_p95_ms=round(percentile(tpots, 0.95), 2),
        tpot_p99_ms=round(percentile(tpots, 0.99), 2),
        itl_p99_ms=round(percentile(all_itls, 0.99), 2),
        ttft_slo_ms=ttft_slo_ms,
        tpot_slo_ms=tpot_slo_ms,
        goodput_ratio=round(good_count / max(1, len(observations)), 4),
        goodput_rps=round(good_count / denom, 2),
    )


async def run_load(
    workload: list[LoadRequestSpec],
    sender: Callable[[LoadRequestSpec], Awaitable[RequestObservation]],
    *,
    qps_target: float,
    ttft_slo_ms: float = 500.0,
    tpot_slo_ms: float = 50.0,
    time_scale: float = 1.0,
) -> tuple[ServingSummary, list[RequestObservation]]:
    """Dispatch `workload` according to Poisson arrival offsets and collect SLO summary."""
    start = time.perf_counter()

    async def launch_one(spec: LoadRequestSpec) -> RequestObservation:
        delay = spec.arrival_offset_s * time_scale - (time.perf_counter() - start)
        if delay > 0:
            await asyncio.sleep(delay)
        return await sender(spec)

    observations = await asyncio.gather(*(launch_one(spec) for spec in workload))
    wall_s = time.perf_counter() - start
    summary = summarize_observations(
        list(observations),
        qps_target=qps_target,
        wall_s=wall_s,
        ttft_slo_ms=ttft_slo_ms,
        tpot_slo_ms=tpot_slo_ms,
    )
    return summary, list(observations)


async def send_openai_sse_request(
    client: httpx.AsyncClient,
    base_url: str,
    model: str,
    spec: LoadRequestSpec,
    api_key: str = "EMPTY",
) -> RequestObservation:
    """Send one streaming Chat Completions request and record TTFT / ITL / TPOT."""
    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    body = {
        "model": model,
        "messages": [{"role": "user", "content": spec.prompt_text}],
        "max_tokens": spec.output_tokens,
        "temperature": 0.0,
        "stream": True,
    }
    t0 = time.perf_counter()
    first_t: float | None = None
    last_t: float | None = None
    itls: list[float] = []
    chunks = 0
    try:
        async with client.stream("POST", url, headers=headers, json=body, timeout=120.0) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[6:].strip()
                if payload == "[DONE]":
                    break
                data = json.loads(payload)
                delta = data.get("choices", [{}])[0].get("delta", {})
                if delta.get("content"):
                    now = time.perf_counter()
                    if first_t is None:
                        first_t = now
                    else:
                        itls.append((now - last_t) * 1000.0)  # type: ignore[operator]
                    last_t = now
                    chunks += 1
        end_t = time.perf_counter()
        ttft_ms = ((first_t or end_t) - t0) * 1000.0
        e2e_ms = (end_t - t0) * 1000.0
        decode_ms = max(0.0, e2e_ms - ttft_ms)
        tpot_ms = decode_ms / max(1, chunks - 1) if chunks > 1 else 0.0
        return RequestObservation(
            req_id=spec.req_id,
            prompt_tokens=spec.prompt_tokens,
            output_tokens=max(chunks, 1),
            ttft_ms=ttft_ms,
            tpot_ms=tpot_ms,
            e2e_ms=e2e_ms,
            itl_ms=itls,
            ok=True,
        )
    except Exception as exc:
        return RequestObservation(
            req_id=spec.req_id,
            prompt_tokens=spec.prompt_tokens,
            output_tokens=0,
            ttft_ms=0.0,
            tpot_ms=0.0,
            e2e_ms=(time.perf_counter() - t0) * 1000.0,
            itl_ms=[],
            ok=False,
            error=str(exc),
        )


def summary_to_dict(summary: ServingSummary) -> dict[str, Any]:
    return asdict(summary)
