"""Programmatically solved tasks. No model, network or torch dependency.

每个任务由两半组成：

    make_task   出题：随机生成题目、算出参考答案、拼出 prompt
    verify      判卷：给一段模型输出，返回 correct + 结构化原因

这里不 import torch，因为判卷逻辑不应该依赖模型环境：数据生成、单元测试、
离线重新判卷都能单独跑。出题器算出的 answer 必须在 make_task 末尾用判卷器验一遍，
两边一旦不一致就直接 raise（见文件底部），而不是等训练完才发现标签是错的。
"""

from __future__ import annotations

import ast
import hashlib
import json
import random
import sqlite3
from collections import Counter, deque
from contextlib import closing
from dataclasses import asdict, dataclass
from fractions import Fraction
from functools import lru_cache

RULE_VERSION = "1"
# AST 节点类型 -> 运算符符号。判卷时只认这四个映射，其它节点一律拒绝
OPS = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/"}


@dataclass(frozen=True)
class Verdict:
    """一次判卷的结果。reason 是给统计用的标签，不是给人看的错题本。"""

    correct: bool
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


def digest(value: object) -> str:
    """内容哈希。先转成规范 JSON（键排序、无空白）再 sha256，

    这样同一内容无论字典插入顺序如何都得到同一个值；task_id、数据 manifest、
    源码哈希都靠它保持一致。
    """
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def solve(numbers: tuple[int, ...], ops: str, integer_only: bool = False) -> dict:
    """Subset DP, one witness per exact result; enumerates all binary partitions.

    做法：用 bitmask 表示“当前用了哪些数字”，solve(mask) 返回
    {可达值: 一个最短表达式}。把 mask 划分成左右两个非空子集，
    再把两边能凑出的值两两组合。

    为什么用 Fraction 而不是 float：除法会产生 1/3 这类无法精确表示的值，
    float 下 1/3*3 != 1，会把正确解判错。

    integer_only=True 只保留整数中间结果，L4 拿它求补集来强制“必须经过分数”。
    每个值只保留最短表达式，用于给出可读的参考答案。
    """

    @lru_cache(None)
    def visit(mask: int) -> dict[Fraction, str]:
        if mask.bit_count() == 1:
            number = numbers[mask.bit_length() - 1]
            return {Fraction(number): str(number)}
        result = {}
        left = (mask - 1) & mask
        while left:
            right = mask ^ left
            if right:
                for a, expr_a in visit(left).items():
                    for b, expr_b in visit(right).items():
                        for op in ops:
                            if op == "/" and not b:
                                continue
                            if op == "+":
                                value = a + b
                            elif op == "-":
                                value = a - b
                            elif op == "*":
                                value = a * b
                            else:
                                value = a / b
                            if integer_only and value.denominator != 1:
                                continue
                            if abs(value.numerator) > 10**8 or value.denominator > 10**8:
                                continue
                            expr = f"({expr_a}{op}{expr_b})"
                            if value not in result or len(expr) < len(result[value]):
                                result[value] = expr
            left = (left - 1) & mask
        return result

    return visit((1 << len(numbers)) - 1)


def countdown_verdict(payload: dict, output: str) -> Verdict:
    """凑数题的判卷：白名单 AST 遍历 + Fraction 精确求值。

    不用 Python 的 ``eval``，因为它会执行任意代码，而且浮点除法会把
    “1/3*3” 这类正确解判错。这里只递归处理两类节点：整数常量与四则 BinOp，
    其余节点一律报 illegal_operation。

    检查顺序是刻意的：先长/复杂度，再语法，再逐节点白名单，最后才是数字用量与结果。
    这样同一个非法输入只拿到一个最具体的标签，统计时不会重复计数。
    """
    text = output.strip()
    if len(text) > 256:
        return Verdict(False, "too_long")
    try:
        tree = ast.parse(text, mode="eval")
    except (SyntaxError, ValueError, RecursionError):
        return Verdict(False, "parse_error")
    if sum(1 for _ in ast.walk(tree)) > 64:
        return Verdict(False, "too_complex")
    used = []

    def evaluate(node: ast.AST) -> Fraction:
        if isinstance(node, ast.Constant) and type(node.value) is int:
            if abs(node.value) > 9999:
                raise ValueError("integer_limit")
            used.append(node.value)
            return Fraction(node.value)
        if not isinstance(node, ast.BinOp) or type(node.op) not in OPS:
            raise ValueError("illegal_operation")
        op = OPS[type(node.op)]
        if op not in payload["ops"]:
            raise ValueError("illegal_operation")
        a, b = evaluate(node.left), evaluate(node.right)
        if op == "+":
            result = a + b
        elif op == "-":
            result = a - b
        elif op == "*":
            result = a * b
        else:
            if not b:
                raise ValueError("division_by_zero")
            result = a / b
        if abs(result.numerator) > 10**8 or result.denominator > 10**8:
            raise ValueError("fraction_limit")
        return result

    try:
        value = evaluate(tree.body)
    except ValueError as exc:
        return Verdict(False, str(exc))
    if Counter(used) != Counter(payload["numbers"]):
        return Verdict(False, "number_mismatch")
    return Verdict(
        value == payload["target"], "correct" if value == payload["target"] else "target"
    )


def maze_solution(grid: list[str]) -> str | None:
    """BFS 求一条从左上角到右下角的最短路径，作为参考答案。

    verifier 不要求最短，所以这里给最短只是为了让 answer 好读；
    真正判卷时绕路的解也算对。返回 U/D/L/R 组成的字符串，无解返回 None。
    """
    n, m = len(grid), len(grid[0])
    queue = deque([(0, 0, "")])
    seen = {(0, 0)}
    while queue:
        r, c, path = queue.popleft()
        if (r, c) == (n - 1, m - 1):
            return path
        for move, dr, dc in [("U", -1, 0), ("D", 1, 0), ("L", 0, -1), ("R", 0, 1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < n and 0 <= nc < m and grid[nr][nc] != "#" and (nr, nc) not in seen:
                seen.add((nr, nc))
                queue.append((nr, nc, path + move))
    return None


def maze_verdict(payload: dict, output: str) -> Verdict:
    """迷宫题判卷：逐格模拟，只看是否停在终点。

    三类标签：
        format       空输出/超长/含 UDLR 以外的字符
        wall         越界或撞墙（一旦发生立即判错，后续字符不再看）
        not_at_goal  路线合法但没走到终点

    刻意不判“路径是否最短”：这个任务的培养目标是“按规则执行动作序列”，
    不是搜索最优解。
    """
    text = output.strip()
    if not text or len(text) > 256 or any(c not in "UDLR" for c in text):
        return Verdict(False, "format")
    r, c = 0, 0
    grid = payload["grid"]
    for move in text:
        dr, dc = {"U": (-1, 0), "D": (1, 0), "L": (0, -1), "R": (0, 1)}[move]
        r, c = r + dr, c + dc
        if not (0 <= r < len(grid) and 0 <= c < len(grid[0])) or grid[r][c] == "#":
            return Verdict(False, "wall")
    correct = (r, c) == (len(grid) - 1, len(grid[0]) - 1)
    return Verdict(correct, "correct" if correct else "not_at_goal")


def sql_result(query: str, seed: int) -> list:
    """A fresh readonly DB per fixture; a VM-step limit bounds candidate execution.

    每个种子新建一个内存库：保证两条 SQL 看到完全相同的数据，且互不影响。
    四重沙箱把“模型输出”当作不可信代码执行：
        1. authorizer 只放行 SELECT/READ/FUNCTION，写、PRAGMA、ATTACH 全部拒绝；
        2. 函数白名单进一步限制到 count/sum/min/max/avg/coalesce；
        3. progress_handler 每 1000 条 VM 指令回调一次，超过 100 次就中止；
        4. 结果超过 1000 行报 row_limit。
    返回前按 repr 排序，这样下游得到的是多重集而不是无序列表。
    """
    rng = random.Random(seed)
    with closing(sqlite3.connect(":memory:")) as db:
        db.execute("CREATE TABLE items (id INTEGER, category TEXT, value INTEGER)")
        rows = [
            (i, rng.choice(["a", "b", "c"]), rng.choice([None, -1, 0, 2, 9, 20, 30, 40, 50]))
            for i in range(30)
        ]
        db.executemany("INSERT INTO items VALUES (?, ?, ?)", rows)
        db.commit()
        # Deny writes, pragmas, attachments, schema changes, and non-whitelisted functions.
        allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION}

        def authorize(action, arg1, arg2, _db, _source):
            if action not in allowed:
                return sqlite3.SQLITE_DENY
            if action == sqlite3.SQLITE_FUNCTION and (arg2 or "").lower() not in {
                "count",
                "sum",
                "min",
                "max",
                "avg",
                "coalesce",
            }:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        db.set_authorizer(authorize)
        calls = 0

        def limit():
            nonlocal calls
            calls += 1
            return calls > 100

        db.set_progress_handler(limit, 1000)
        result = db.execute(query).fetchmany(1001)
        if len(result) > 1000:
            raise ValueError("row_limit")
        return sorted(result, key=repr)


def sql_verdict(payload: dict, output: str) -> Verdict:
    """SQL 题判卷：四个 fixture 上执行，结果多重集全部一致才算对。

    标签：
        format          不以 SELECT 开头或超长（最便宜的前置检查）
        sql_error       语法/权限/超限等执行失败
        result_mismatch  能跑但结果与参考 SQL 不同

    参考 SQL 自己抛错属于基础设施故障，直接向上抛而不计入模型失败：
    否则数据/环境的问题会被统计成“模型不会写 SQL”。
    """
    query = output.strip()
    if len(query) > 1024 or not query.lower().startswith("select "):
        return Verdict(False, "format")
    for seed in payload["fixtures"]:
        # Errors in reference SQL are infrastructure failures, not model failures.
        expected = sql_result(payload["reference"], seed)
        try:
            actual = sql_result(query, seed)
        except (sqlite3.Error, ValueError):
            return Verdict(False, "sql_error")
        if actual != expected:
            return Verdict(False, "result_mismatch")
    return Verdict(True, "correct")


def verify(task: dict, output: str) -> Verdict:
    verifier = {"countdown": countdown_verdict, "maze": maze_verdict, "sql": sql_verdict}
    return verifier[task["task"]](task["payload"], output)


def make_task(kind: str, rng: random.Random, difficulty: str = "L2", ood: bool = False) -> dict:
    """生成一道题：题目、prompt、参考答案、task_id 一次算齐。

    ood=True 时只改参数范围（数字更大、网格更大、阈值段不同），不改任务形式，
    用来检验“同一套规则能否外推到没见过的数值段”。
    """
    if kind == "countdown":
        # L1-L4 只属于 countdown：数字个数与允许运算符逐级放宽，
        # L4 额外要求解法必须经过分数中间值
        count, ops = {"L1": (2, "+-"), "L2": (3, "+-*"), "L3": (4, "+-*/"), "L4": (4, "+-*/")}[
            difficulty
        ]
        for _ in range(1000):
            numbers = tuple(
                sorted(rng.randint(16 if ood else 1, 25 if ood else 15) for _ in range(count))
            )
            answers = solve(numbers, ops)
            # L4 先用 integer_only=True 求“只用整数中间结果能到哪里”，
            # 再要求 target 不在这个集合里——于是任何正确解必然出现分数
            integer_answers = solve(numbers, ops, True) if difficulty == "L4" else {}
            targets = sorted(
                v
                for v in answers
                if v.denominator == 1
                and 1 <= v <= 200
                and (difficulty != "L4" or v not in integer_answers)
            )
            if targets:
                target = rng.choice(targets)
                break
        else:
            raise RuntimeError("Failed to generate solvable countdown task")
        payload = {"numbers": list(numbers), "target": int(target), "ops": ops}
        prompt = (
            f"Use each number in {list(numbers)} exactly once to make {int(target)}. "
            f"Allowed binary operators: {' '.join(ops)} and parentheses. "
            "Output one expression only, without an equals sign or explanation."
        )
        answer = answers[target]
    elif kind == "maze":
        # 28% 的格子随机放墙，再在左上加 S、右下加 G；
        # 生成失败（S 到 G 不连通）就重抽，最多 1000 次
        size = 5 if ood else 4
        for _ in range(1000):
            cells = [
                ["#" if rng.random() < 0.28 else "." for _ in range(size)] for _ in range(size)
            ]
            cells[0][0], cells[-1][-1] = "S", "G"
            grid = ["".join(row) for row in cells]
            answer = maze_solution(grid)
            if answer:
                break
        else:
            raise RuntimeError("Failed to generate solvable maze")
        payload = {"grid": grid}
        prompt = (
            "Move from S to G in this grid. # is a wall. "
            "Output only a sequence of U,D,L,R characters.\n" + "\n".join(grid)
        )
    elif kind == "sql":
        # 题目空间 = 5 种聚合 x 3 个 category x 6 种比较符 x 阈值取值，
        # 共几千个点；难度用阈值区间区分，而不是换一种题型
        threshold = rng.randint(21, 40) if ood else rng.randint(-5, 20)
        category = rng.choice(["a", "b", "c"])
        aggregate = rng.choice(["COUNT(*)", "SUM(value)", "MAX(value)", "MIN(value)", "AVG(value)"])
        operator = rng.choice([">", "<", ">=", "<=", "=", "!="])
        reference = (
            f"SELECT {aggregate} FROM items WHERE category = '{category}' "
            f"AND value {operator} {threshold}"
        )
        payload = {"reference": reference, "fixtures": [rng.randrange(2**31) for _ in range(4)]}
        prompt = (
            "SQLite table items(id INTEGER, category TEXT, value INTEGER). "
            f"Return {aggregate} for rows with category '{category}' and value "
            f"{operator} {threshold}. Output one SELECT statement only."
        )
        answer = reference
    else:
        raise ValueError(f"Unknown task: {kind}")
    # SQL fixture seeds do not create new questions or new split identities.
    # task_id 只由“任务类型 + 判卷规则版本 + 题目内容”决定：
    # 不含随机种子与 prompt 文字，所以同一道题在任何 run 里 id 相同，配对比较才能对齐
    identity = payload["reference"] if kind == "sql" else payload
    task = {
        "task_id": digest([kind, RULE_VERSION, identity]),
        "task": kind,
        "difficulty": difficulty,
        "payload": payload,
        "prompt": prompt,
        "answer": answer,
    }
    if not verify(task, answer).correct:
        raise RuntimeError("Solver/verifier disagreement")
    return task
