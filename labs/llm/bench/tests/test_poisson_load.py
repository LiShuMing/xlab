"""Unit tests for M3.2 Poisson online serving load generator & SLO Goodput metrics."""

from __future__ import annotations

import asyncio
import unittest

from llm_benchmark.poisson_load import (
    LoadRequestSpec,
    RequestObservation,
    generate_poisson_workload,
    run_load,
    summarize_observations,
)


class PoissonLoadTests(unittest.TestCase):
    def test_poisson_workload_is_deterministic_and_monotonic(self) -> None:
        w1 = generate_poisson_workload(20, qps=5.0, seed=7)
        w2 = generate_poisson_workload(20, qps=5.0, seed=7)
        self.assertEqual(w1, w2)
        offsets = [r.arrival_offset_s for r in w1]
        self.assertEqual(offsets, sorted(offsets))
        self.assertEqual(offsets[0], 0.0)
        # Mixed short and long prompt lengths must both appear.
        self.assertTrue(any(r.prompt_tokens <= 128 for r in w1))
        self.assertTrue(any(r.prompt_tokens >= 384 for r in w1))

    def test_goodput_separates_raw_throughput_from_slo_violations(self) -> None:
        obs = [
            RequestObservation(0, 64, 32, ttft_ms=120.0, tpot_ms=20.0, e2e_ms=760.0, itl_ms=[20.0] * 31),
            RequestObservation(1, 512, 32, ttft_ms=820.0, tpot_ms=25.0, e2e_ms=1620.0, itl_ms=[25.0] * 31),
            RequestObservation(2, 64, 32, ttft_ms=150.0, tpot_ms=70.0, e2e_ms=2390.0, itl_ms=[70.0] * 31),
            RequestObservation(3, 64, 32, ttft_ms=180.0, tpot_ms=30.0, e2e_ms=1140.0, itl_ms=[30.0] * 31),
        ]
        summary = summarize_observations(
            obs, qps_target=2.0, wall_s=2.0, ttft_slo_ms=500.0, tpot_slo_ms=50.0
        )
        # Only req 0 and req 3 meet BOTH TTFT <= 500ms and TPOT <= 50ms.
        self.assertEqual(summary.num_ok, 4)
        self.assertAlmostEqual(summary.goodput_ratio, 0.5)
        self.assertAlmostEqual(summary.goodput_rps, 1.0)
        self.assertAlmostEqual(summary.achieved_rps, 2.0)
        self.assertEqual(summary.itl_p99_ms, 70.0)

    def test_run_load_async_dispatches_all_requests(self) -> None:
        workload = generate_poisson_workload(6, qps=200.0, seed=11)

        async def fake_sender(spec: LoadRequestSpec) -> RequestObservation:
            await asyncio.sleep(0.002)
            return RequestObservation(
                req_id=spec.req_id,
                prompt_tokens=spec.prompt_tokens,
                output_tokens=spec.output_tokens,
                ttft_ms=50.0,
                tpot_ms=10.0,
                e2e_ms=50.0 + 10.0 * spec.output_tokens,
                itl_ms=[10.0] * max(1, spec.output_tokens - 1),
            )

        summary, obs = asyncio.run(
            run_load(workload, fake_sender, qps_target=200.0, ttft_slo_ms=100.0, tpot_slo_ms=20.0)
        )
        self.assertEqual(len(obs), 6)
        self.assertEqual(summary.goodput_ratio, 1.0)


if __name__ == "__main__":
    unittest.main()
