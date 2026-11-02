"""Focused tests: hand-computed oracles, actual spawn, protocol and CLI safety."""

import copy
import json
import multiprocessing as mp
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from distributed_kmeans import (  # noqa: E402
    Fault,
    WorkerFailure,
    _local_stats,
    _reduce_round,
    fit_kmeans,
    make_dataset,
)


def _assert_reaped(pids, codes):
    assert pids and all(code is not None for code in codes)
    assert not set(pids) & {child.pid for child in mp.active_children()}


def test_hand_calculated_weighted_mean_with_uneven_shards():
    points = np.array([[0.0], [10.0], [10.0], [10.0]])
    for workers, sizes in [(0, None), (2, (1, 3))]:
        result = fit_kmeans(points, [[0.0]], workers=workers, shard_sizes=sizes)
        np.testing.assert_array_equal(result.centers, [[7.5]])
        np.testing.assert_array_equal(result.counts, [4])
        assert result.sse == 75.0
        if workers:
            _assert_reaped(result.worker_pids, result.worker_exitcodes)


def test_hand_calculated_separated_clusters():
    result = fit_kmeans([[0.0], [2.0], [8.0], [10.0]], [[0.0], [10.0]], workers=2)
    np.testing.assert_array_equal(result.centers, [[1.0], [9.0]])
    np.testing.assert_array_equal(result.labels, [0, 0, 1, 1])
    assert result.sse == 4.0
    assert result.converged


@pytest.mark.parametrize("workers", [2, 4])
def test_partition_equivalence_and_distinct_persistent_processes(workers):
    points, initial = make_dataset(1000)
    baseline = fit_kmeans(points, initial)
    parallel = fit_kmeans(points, initial, workers=workers, batch_size=7)
    np.testing.assert_allclose(parallel.centers, baseline.centers, rtol=1e-6, atol=1e-8)
    np.testing.assert_array_equal(parallel.labels, baseline.labels)
    assert parallel.sse == pytest.approx(baseline.sse)
    assert len(set(parallel.worker_pids)) == workers
    assert os.getpid() not in parallel.worker_pids
    _assert_reaped(parallel.worker_pids, parallel.worker_exitcodes)
    assert all(code == 0 for code in parallel.worker_exitcodes)
    # Same process set is started once; every round covers every shard.
    for row in parallel.history:
        assert tuple(worker["pid"] for worker in row["workers"]) == parallel.worker_pids
        assert [worker["shard_id"] for worker in row["workers"]] == list(range(workers))
        assert sum(row["counts"]) == len(points)
        assert row["sent_payload_bytes"] > 0 and row["received_payload_bytes"] > 0
    objective = [row["sse_before_update"] for row in parallel.history] + [parallel.sse]
    assert all(
        right <= left + max(1e-8, left * 1e-12) for left, right in zip(objective, objective[1:])
    )


def test_empty_shards_when_workers_exceed_samples():
    result = fit_kmeans([[0.0], [10.0]], [[0.0], [10.0]], workers=4)
    assert result.shard_sizes == (1, 1, 0, 0)
    np.testing.assert_array_equal(result.counts, [1, 1])
    assert result.sse == 0.0


def test_duplicate_points_empty_cluster_and_tie_break():
    result = fit_kmeans([[1.0], [1.0], [1.0]], [[1.0], [1.0]], workers=2)
    np.testing.assert_array_equal(result.labels, [0, 0, 0])
    np.testing.assert_array_equal(result.counts, [3, 0])
    np.testing.assert_array_equal(result.centers, [[1.0], [1.0]])
    result = fit_kmeans([[0.0], [2.0]], [[0.0], [100.0]])
    assert result.centers[1, 0] == 100.0


def test_k_equals_n_and_final_evaluation_after_iteration_limit():
    result = fit_kmeans([[0.0], [1.0], [4.0], [10.0]], [[0.0], [4.0]], max_iter=1)
    assert not result.converged
    expected_distances = np.square(
        np.array([[0.0], [1.0], [4.0], [10.0]])[:, None, :] - result.centers[None, :, :]
    ).sum(axis=2)
    np.testing.assert_array_equal(result.labels, expected_distances.argmin(axis=1))
    assert result.sse == pytest.approx(expected_distances.min(axis=1).sum())
    assert result.sse != result.history[-1]["sse_before_update"]
    exact = fit_kmeans([[1.0], [2.0]], [[1.0], [2.0]])
    assert exact.converged and exact.sse == 0.0


@pytest.mark.parametrize(
    "points, centers",
    [
        ([], [[0.0]]),
        ([[0.0]], []),
        ([0.0], [[0.0]]),
        ([[0.0]], [[0.0], [1.0]]),
        ([[0.0]], [[0.0, 1.0]]),
        ([[float("nan")]], [[0.0]]),
        ([[0.0]], [[float("inf")]]),
        (np.zeros((2, 1025)), np.zeros((1, 1025))),
        (np.zeros((1_000_001, 2)), [[0.0, 0.0]]),
    ],
)
def test_invalid_inputs_fail_before_spawning(points, centers):
    before = {p.pid for p in mp.active_children()}
    with pytest.raises(ValueError):
        fit_kmeans(points, centers, workers=2)
    assert before == {p.pid for p in mp.active_children()}


@pytest.mark.parametrize(
    "options",
    [
        {"workers": -1},
        {"workers": 33},
        {"workers": True},
        {"workers": 1.5},
        {"max_iter": 0},
        {"tol": -1},
        {"tol": float("nan")},
        {"batch_size": 0},
        {"round_timeout": 0},
        {"round_timeout": float("inf")},
        {"workers": 2, "shard_sizes": [1]},
        {"workers": 2, "shard_sizes": [0, 0]},
        {"workers": 2, "shard_sizes": [True, 0]},
        {"fault": Fault()},
        {"workers": 2, "fault": Fault(worker_id=2)},
        {"workers": 2, "fault": Fault(action="retry")},
        {"workers": 2, "fault": Fault(seconds=float("nan"))},
    ],
)
def test_invalid_options(options):
    with pytest.raises(ValueError):
        fit_kmeans([[0.0]], [[0.0]], **options)


def test_overflow_is_failure_not_nan_success():
    with pytest.raises((FloatingPointError, ValueError)):
        fit_kmeans([[1e308]], [[-1e308]])
    with pytest.raises(WorkerFailure) as caught:
        fit_kmeans([[1e308]], [[-1e308]], workers=2)
    _assert_reaped(caught.value.worker_pids, caught.value.worker_exitcodes)


def _messages():
    centers = np.array([[0.0]])
    messages = [
        {"shard_id": i, "round_id": 0, **_local_stats(np.array([[float(i)]]), centers, 1024)}
        for i in range(2)
    ]
    return centers, messages


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "stale", "counts", "nan", "shape"])
def test_reduction_rejects_invalid_complete_round(mutation):
    centers, messages = _messages()
    if mutation == "missing":
        messages.pop()
    elif mutation == "duplicate":
        messages[1] = copy.deepcopy(messages[0])
    elif mutation == "stale":
        messages[1]["round_id"] = -1
    elif mutation == "counts":
        messages[1]["counts"][0] = 0
    elif mutation == "nan":
        messages[1]["sse"] = float("nan")
    elif mutation == "shape":
        messages[1]["sums"] = np.array([[1.0, 2.0]])
    with pytest.raises(WorkerFailure):
        _reduce_round(messages, (1, 1), centers, 0)


def test_reduction_is_ordered_not_arrival_dependent():
    centers, messages = _messages()
    first, counts, _ = _reduce_round(messages, (1, 1), centers, 0)
    second, _, _ = _reduce_round(list(reversed(messages)), (1, 1), centers, 0)
    np.testing.assert_array_equal(first, [[0.5]])
    np.testing.assert_array_equal(first, second)
    np.testing.assert_array_equal(counts, [2])


@pytest.mark.parametrize(
    "fault, timeout, expected",
    [
        (Fault(action="exit"), 30.0, "worker"),
        (Fault(action="stale"), 30.0, "round_id"),
        (Fault(seconds=2.0), 0.1, "stats timeout"),
    ],
)
def test_fault_propagation_and_cleanup(fault, timeout, expected):
    points, initial = make_dataset(100)
    before = {p.pid for p in mp.active_children()}
    with pytest.raises(WorkerFailure, match=expected) as caught:
        fit_kmeans(points, initial, workers=4, fault=fault, round_timeout=timeout)
    _assert_reaped(caught.value.worker_pids, caught.value.worker_exitcodes)
    assert {p.pid for p in mp.active_children()} == before


def test_straggler_delays_barrier_without_changing_result():
    points, initial = make_dataset(100)
    baseline = fit_kmeans(points, initial)
    result = fit_kmeans(points, initial, workers=2, fault=Fault(seconds=0.1))
    assert result.history[0]["round_seconds"] >= 0.1
    assert result.history[0]["workers"][0]["delay_seconds"] == 0.1
    np.testing.assert_array_equal(result.labels, baseline.labels)
    np.testing.assert_allclose(result.centers, baseline.centers)


def test_iteration_broadcast_size_does_not_grow_with_input_rows():
    sent = []
    for rows in (10, 10000):
        points, initial = make_dataset(rows)
        result = fit_kmeans(points, initial, workers=2, max_iter=1)
        sent.append(result.history[0]["sent_payload_bytes"])
    assert sent[0] == sent[1] > 0


@pytest.mark.parametrize("kind", ["startup", "interrupt"])
def test_startup_failure_and_interrupt_reap_owned_workers(monkeypatch, kind):
    import distributed_kmeans as module

    original = module._collect
    before = {p.pid for p in mp.active_children()}

    def interrupted(connections, processes, timeout, phase):
        if kind == "startup":
            raise WorkerFailure("injected ready failure")
        if phase == "stats":
            raise KeyboardInterrupt()
        return original(connections, processes, timeout, phase)

    monkeypatch.setattr(module, "_collect", interrupted)
    with pytest.raises(WorkerFailure if kind == "startup" else KeyboardInterrupt):
        fit_kmeans([[0.0], [10.0]], [[0.0]], workers=2)
    assert {p.pid for p in mp.active_children()} == before


def test_acceptance_gate_is_active_under_optimized_python():
    result = subprocess.run(
        [
            sys.executable,
            "-O",
            "-c",
            "from distributed_kmeans import _require; _require(False, 'expected gate failure')",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0
    assert "expected gate failure" in result.stderr


def test_fixed_random_initialization_is_not_a_global_optimum_guarantee():
    points, random_initial = make_dataset(10000)
    baseline = fit_kmeans(points, random_initial)
    controlled = fit_kmeans(points, points[:3])
    assert baseline.converged and controlled.converged
    assert controlled.sse < baseline.sse
    np.testing.assert_array_equal(controlled.counts, [3334, 3333, 3333])


def _cli(*args):
    return subprocess.run(
        [sys.executable, str(ROOT / "distributed_kmeans.py"), *map(str, args)],
        capture_output=True,
        text=True,
        timeout=45,
    )


def test_cli_invalid_input_and_existing_output_are_not_modified(tmp_path):
    output = tmp_path / "must-not-exist"
    result = _cli("--rows", "0", "--output", output)
    assert result.returncode == 2 and not output.exists()
    existing = tmp_path / "existing"
    existing.mkdir()
    marker = existing / "user.txt"
    marker.write_text("keep", encoding="utf-8")
    result = _cli("--rows", "10", "--output", existing)
    assert result.returncode == 2
    assert marker.read_text(encoding="utf-8") == "keep"
    assert sorted(p.name for p in existing.iterdir()) == ["user.txt"]


def test_cli_full_matrix_and_evidence(tmp_path):
    output = tmp_path / "evidence"
    result = _cli("--rows", "100", "--output", output)
    assert result.returncode == 0, result.stdout + result.stderr
    record = json.loads(
        (output / "result.json").read_text(encoding="utf-8"),
        parse_constant=lambda value: pytest.fail(f"nonfinite JSON: {value}"),
    )
    assert record["status"] == "passed"
    assert set(record["runs"]) == {"serial", "processes-2", "processes-4", "uneven-4", "slow-4"}
    assert set(record["expected_failures"]) == {"exit", "stale", "timeout"}
    assert all(row["status"] == "observed" for row in record["expected_failures"].values())
    assert "状态：passed" in (output / "report.md").read_text(encoding="utf-8")
    assert "input_sha256" in record and "code_sha256" in record
    assert record["initialization_control"]["result"]["converged"]
    assert "Evidence:" in result.stdout


def test_cli_unexpected_failure_is_not_a_success_report(tmp_path, monkeypatch):
    import distributed_kmeans as module

    def fail(rows, record):
        raise RuntimeError("injected suite failure")

    monkeypatch.setattr(module, "run_experiments", fail)
    output = tmp_path / "failed"
    assert module.main(["--output", str(output)]) == 1
    assert json.loads((output / "result.json").read_text())["status"] == "failed"
    assert "状态：failed" in (output / "report.md").read_text(encoding="utf-8")


def test_default_output_symlink_is_rejected(tmp_path, monkeypatch):
    import distributed_kmeans as module

    target = tmp_path / "target"
    target.mkdir()
    project = tmp_path / "project"
    project.mkdir()
    (project / ".local").symlink_to(target, target_is_directory=True)
    monkeypatch.setattr(module, "__file__", str(project / "distributed_kmeans.py"))
    with pytest.raises(SystemExit) as caught:
        module.main([])
    assert caught.value.code == 2
    assert list(target.iterdir()) == []
