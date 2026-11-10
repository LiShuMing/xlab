"""Native policies vs slow models; deterministic benchmark and reference contracts."""

import json
from pathlib import Path
import random
import subprocess
import sys
import unittest

from oracle import Model

PROBE, BENCH = sys.argv[1:3]
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from run import validate


def benchmark(algorithm: str, workload: str = "hot_shift", capacity: int = 32) -> dict:
    result = subprocess.run(
        [
            BENCH,
            "--algorithm",
            algorithm,
            "--workload",
            workload,
            "--capacity",
            str(capacity),
            "--count",
            "2048",
            "--window-size",
            "256",
            "--repeats",
            "1",
            "--batch-ms",
            "1",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )
    record = json.loads(result.stdout)
    validate(record, {"count": 2048, "repeats": 1})
    return record


class PolicyContracts(unittest.TestCase):
    def test_differential_models(self):
        comparisons = 0
        for seed in (42, 1729):
            rng = random.Random(seed)
            trace = [rng.randrange(16) for _ in range(300)]
            trace += list(range(256)) + [rng.randrange(32, 48) for _ in range(300)]
            trace += [0, (1 << 64) - 1, 0, (1 << 64) - 1] * 8
            text = "\n".join(map(str, trace))
            for algorithm in ("fifo", "lru", "lfu", "slru", "wtinylfu", "arc"):
                for capacity in (0, 1, 2, 7, 32, 128):
                    variants = [(1, 80, 10)]
                    if algorithm == "wtinylfu":
                        variants += [(20, 50, 2), (10, 90, 40)]
                    for window, protected, aging in variants:
                        with self.subTest(
                            seed=seed,
                            algorithm=algorithm,
                            capacity=capacity,
                            parameters=(window, protected, aging),
                        ):
                            model = Model(algorithm, capacity, window, protected, aging)
                            expected = "".join("1" if model.access(key) else "0" for key in trace)
                            result = subprocess.run(
                                [
                                    PROBE,
                                    algorithm,
                                    str(capacity),
                                    str(window),
                                    str(protected),
                                    str(aging),
                                ],
                                input=text,
                                check=True,
                                capture_output=True,
                                text=True,
                                timeout=10,
                            )
                            actual = json.loads(result.stdout)
                            self.assertEqual(actual["hits"], expected)
                            self.assertEqual(actual["resident"], model.resident())
                            comparisons += len(trace)
        print(f"Differential checks: {comparisons} requests across 96 native/model traces")

    def test_actual_benchmark_replay_and_reference(self):
        algorithms = ["fifo", "lru", "lfu", "slru", "wtinylfu", "arc", "reference-lru"]
        records = {algorithm: benchmark(algorithm) for algorithm in algorithms}
        self.assertEqual(len({r["trace_hash"] for r in records.values()}), 1)
        other_capacity = benchmark("lru", capacity=128)
        self.assertEqual(other_capacity["trace_hash"], records["lru"]["trace_hash"])
        self.assertEqual(records["lru"]["hit_digest"], records["reference-lru"]["hit_digest"])
        for algorithm in algorithms:
            cold = benchmark(algorithm, "one_hit")
            self.assertEqual(cold["hits"], 0)
            self.assertIsNone(cold["latency"]["hit"]["p99"])
        for record in records.values():
            self.assertEqual(record["latency"]["all"]["count"], 2048)
            self.assertGreater(record["samples"][0]["cpu_ns_per_op"], 0)

    def test_invalid_parameters(self):
        for args in (
            ["--capacity", "-1"],
            ["--protected-percent", "100"],
            ["--aging-factor", "0"],
            ["--algorithm", "missing"],
            ["--batch-ms", "nan"],
            ["--window-size", "0"],
        ):
            result = subprocess.run([BENCH, *args], capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
