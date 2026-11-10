import json
import random
import sqlite3

import pytest

from reasoning_lab.data import generate_dataset, load_dataset
from reasoning_lab.tasks import countdown_verdict, make_task, solve, sql_result, verify


@pytest.mark.parametrize(
    "expression,reason",
    [
        ("(7+3)*2", "correct"),
        ("7+3+2", "target"),
        ("20", "number_mismatch"),
        ("(7+3)*2 = 20", "parse_error"),
        ("__import__('os').system('id')", "illegal_operation"),
        ("2**3", "illegal_operation"),
        ("-2+3+7", "illegal_operation"),
        ("True+3+7", "illegal_operation"),
        ("(7+3)/0", "division_by_zero"),
    ],
)
def test_countdown_protocol(expression, reason):
    payload = {"numbers": [2, 3, 7], "target": 20, "ops": "+-*/"}
    assert countdown_verdict(payload, expression).reason == reason


def test_duplicates_and_fractional_intermediates():
    payload = {"numbers": [3, 3, 8, 8], "target": 24, "ops": "+-*/"}
    assert countdown_verdict(payload, "8/(3-8/3)").correct
    assert not countdown_verdict(payload, "8+8+8").correct
    assert 24 in solve((3, 3, 8, 8), "+-*/")
    assert 24 not in solve((3, 3, 8, 8), "+-*/", integer_only=True)


@pytest.mark.parametrize("kind", ["countdown", "maze", "sql"])
def test_solver_witnesses(kind):
    rng = random.Random(4)
    for _ in range(12):
        task = make_task(kind, rng)
        assert verify(task, task["answer"]).correct
        assert not verify(task, "invalid output").correct


def test_sql_readonly_and_vm_limit():
    for query in [
        "DELETE FROM items",
        "ATTACH DATABASE '/tmp/out' AS other",
        "SELECT load_extension('anything')",
        "SELECT randomblob(1000000000)",
    ]:
        with pytest.raises(sqlite3.Error):
            sql_result(query, 42)


def test_dataset_disjoint_immutable_and_checked(tmp_path):
    directory = tmp_path / "data"
    generate_dataset(directory, "countdown", 42, {"train": 30, "dev": 10, "test": 10, "ood": 10})
    seen = set()
    for split in ["train", "dev", "test", "ood"]:
        rows = load_dataset(directory, split)
        keys = {row["task_id"] for row in rows}
        assert not keys & seen
        seen.update(keys)
    with pytest.raises(FileExistsError):
        generate_dataset(directory, "countdown", 42, {"train": 1})
    rows = load_dataset(directory, "train")
    rows[0]["answer"] = "wrong"
    (directory / "train.jsonl").write_text("\n".join(json.dumps(row) for row in rows))
    with pytest.raises(ValueError, match="checksum"):
        load_dataset(directory, "train")
