#!/usr/bin/env python3
"""Source mirrors, editorial deduplication, and evidence-based reading progress."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
INTERVALS = (1, 3, 7, 14)
LEVELS = {"read": 1, "practiced": 2, "mastered": 3}
EVENT_PATTERN = re.compile(
    r"https://github\.com/([\w.-]+/[\w.-]+)/pull/(\d+)"
    r"|https://openjdk\.org/jeps/(\d+)"
    r"|https?://[^\s)]+/(P\d+)(?:R\d+)?(?:\.html|\.pdf)",
    re.IGNORECASE,
)


def read_json(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def local(root: Path) -> Path:
    return root / ".local/engineering-daily"


def public_file(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    path.relative_to(root.resolve())
    if local(root).resolve() in path.parents or not path.is_file():
        raise ValueError(f"公开引用必须是存在的仓库文档: {relative}")
    return path


def editions(root: Path, before: date) -> list[dict[str, Any]]:
    result = []
    for path in sorted((root / "docs/daily/editions").glob("*.json")):
        record = read_json(path)
        if date.fromisoformat(record["date"]) < before:
            record = dict(record, ledger_path=str(path.relative_to(root)))
            result.append(record)
    return result


def legacy_events(root: Path, before: date) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for directory in ("github-daily", "email-digest"):
        for path in sorted((root / "docs" / directory).glob("*.md")):
            try:
                published = date.fromisoformat(path.name[:10])
            except ValueError:
                continue
            if published >= before:
                continue
            for match in EVENT_PATTERN.finditer(path.read_text(encoding="utf-8")):
                repo, number, jep, proposal = match.groups()
                identity = (f"github:{repo.lower()}:pr:{number}" if repo else
                            f"jep:{jep}" if jep else f"wg21:{proposal.upper()}")
                references = result.setdefault(identity, [])
                reference = str(path.relative_to(root))
                if reference not in references:
                    references.append(reference)
    return result


def history(root: Path, day: date) -> dict[str, Any]:
    records = editions(root, day)
    events = legacy_events(root, day)
    for record in records:
        for item in record.get("news", []):
            events.setdefault(item["event_id"], []).append(record["report"])
    return {"before": day.isoformat(), "events": events, "editions": records}


def plan(root: Path, day: date) -> dict[str, Any]:
    curriculum = read_json(root / "docs/daily/projects/highway/curriculum.json")
    records = editions(root, day)
    state = read_json(local(root) / "progress.json", {"units": {}})["units"]
    # Later feedback must not affect a historical planning query.
    state = {key: value for key, value in state.items() if value["date"] <= day.isoformat()}
    issued = {record["lesson"]["unit_id"] for record in records}
    pending = [unit for unit in curriculum["units"] if unit["id"] in issued
               and LEVELS.get(state.get(unit["id"], {}).get("level", ""), 0) < 2]
    due = [{"id": key, "due": value["next_review"], "level": value["level"]}
           for key, value in state.items()
           if value.get("next_review") and value["next_review"] <= day.isoformat()]
    due.sort(key=lambda item: (item["due"], item["id"]))
    curriculum_ids = {unit["id"] for unit in curriculum["units"]}
    due_lesson = next((item for item in due if item["id"] in curriculum_ids), None)
    next_unit = next((unit for unit in curriculum["units"] if unit["id"] not in issued), None)
    if len(pending) >= curriculum["max_pending"]:
        selection = {"mode": "remediation", "unit": pending[0], "reason": "待实践课程达到上限"}
    elif due_lesson:
        selection = {"mode": "review", "unit_id": due_lesson["id"], "reason": "到期复习优先"}
    else:
        selection = {"mode": "new" if next_unit else "review", "unit": next_unit,
                     "reason": "下一知识单元" if next_unit else "主线已生成完毕，等待实际复盘"}
    return {"date": day.isoformat(), "selection": selection,
            "pending_practice": [unit["id"] for unit in pending], "due_reviews": due,
            "exercise_domain": ("C++", "Java/JVM", "Linux", "系统设计", "算法", "排障", "复习")[day.weekday()],
            "recent_exercises": [record["exercise"] for record in records
                                 if (day - date.fromisoformat(record["date"])).days <= 14]}


def check(root: Path, path: Path) -> dict[str, Any]:
    record = read_json(path)
    day = date.fromisoformat(record["date"])
    if record["schema_version"] != 1 or record["timezone"] != "Asia/Shanghai":
        raise ValueError("清单需要schema_version=1、timezone=Asia/Shanghai")
    cutoff = datetime.fromisoformat(record["cutoff_at"])
    if cutoff.utcoffset() is None or cutoff.astimezone(ZoneInfo("Asia/Shanghai")).date() != day:
        raise ValueError("截止时间必须含时区并对应报告日期")
    public_file(root, record["report"])
    lesson = record["lesson"]
    curriculum = read_json(root / "docs/daily/projects/highway/curriculum.json")
    if lesson["unit_id"] not in {unit["id"] for unit in curriculum["units"]}:
        raise ValueError("未知知识单元")
    public_file(root, lesson["path"])
    public_file(root, record["exercise"]["path"])
    records = editions(root, day)
    previous_lessons = {item["lesson"]["unit_id"] for item in records}
    if lesson["mode"] == "new":
        if plan(root, day)["selection"]["mode"] != "new" and not record.get("progress_override"):
            raise ValueError("当前应先复习/补救；推进新课须记录用户要求或新的反馈依据")
        if lesson["unit_id"] in previous_lessons:
            raise ValueError("已生成的知识单元不能再次标为新课")
        if not lesson.get("novelty", "").strip():
            raise ValueError("新课必须说明知识增量")
        expected = next((unit["id"] for unit in curriculum["units"]
                         if unit["id"] not in previous_lessons), None)
        if lesson["unit_id"] != expected:
            raise ValueError(f"主线下一单元应为 {expected}")
    elif lesson["mode"] in ("review", "remediation"):
        if lesson["unit_id"] not in previous_lessons or not lesson.get("reason", "").strip():
            raise ValueError("复习/补救必须引用已生成单元并解释原因")
    else:
        raise ValueError("课程mode只能是new/review/remediation")
    prior_events = legacy_events(root, day)
    identities = set()
    for event in record["news"]:
        identity = event["event_id"]
        if identity.startswith("github:") and identity != identity.lower():
            raise ValueError("GitHub事件身份统一使用小写owner/repo")
        if not re.fullmatch(r"github:[\w.-]+/[\w.-]+:pr:\d+|jep:\d+|wg21:P\d+|release:[\w./:+-]+", identity):
            raise ValueError(f"事件身份不规范: {identity}")
        if identity in identities:
            raise ValueError(f"同日重复事件: {identity}")
        identities.add(identity)
        if not event.get("stage") or not event.get("delta_key") or not event.get("delta"):
            raise ValueError(f"事件缺阶段或技术增量: {identity}")
        if date.fromisoformat(event["event_date"]) > day:
            raise ValueError("不能报道未来事件")
        if not event.get("sources") or not all(source.startswith("https://") for source in event["sources"]):
            raise ValueError("动态需要原始HTTPS来源")
        prior = [old for item in records for old in item["news"] if old["event_id"] == identity]
        if any(old["stage"] == event["stage"] and old["delta_key"] == event["delta_key"] for old in prior):
            raise ValueError(f"事件阶段与技术增量没有变化: {identity}")
        if identity in prior_events or prior:
            valid_previous = set(prior_events.get(identity, [])) | {
                item["report"] for item in records
                if any(old["event_id"] == identity for old in item["news"])}
            if event.get("previous") not in valid_previous:
                raise ValueError(f"重访事件必须链接对应旧报道: {identity}")
            public_file(root, event["previous"])
    exercise = record["exercise"]
    same_skill = [item for item in records if
                  (day - date.fromisoformat(item["date"])).days <= 14
                  and item["exercise"]["skill_key"] == exercise["skill_key"]]
    if exercise["mode"] not in ("new", "review", "remediation", "variant"):
        raise ValueError("未知练习模式")
    if exercise["mode"] != "new" or same_skill:
        if exercise["mode"] == "new":
            raise ValueError("14天内同能力题必须标明复习、补救或进阶变式")
        if exercise.get("previous") not in {item["exercise"]["path"] for item in records}:
            raise ValueError("复习/变式必须引用以前的题目")
        if not exercise.get("reason", "").strip():
            raise ValueError("复习/变式必须说明原因或新的要求")
    # A familiar skill can receive a new id, but an old problem is never a new exercise.
    if exercise["mode"] == "new" and any(item["exercise"]["id"] == exercise["id"] for item in records):
        raise ValueError("旧题不能再次标为新题")
    recall = record.get("recall")
    if recall and recall.get("unit_id") and recall["unit_id"] not in previous_lessons:
        raise ValueError("回忆题不能引用尚未生成的旧课")
    return {"ok": True, "date": day.isoformat(), "news": len(record["news"]),
            "note": "仅验证结构与历史身份；语义重复、证据质量、答案隐藏仍需人工检查"}


def feedback(root: Path, args: argparse.Namespace) -> dict[str, Any]:
    root = root.resolve()
    evidence = (root / args.evidence).resolve()
    evidence.relative_to(local(root).resolve())
    if not evidence.is_file() or not evidence.read_text(encoding="utf-8").strip():
        raise ValueError("需要.local/engineering-daily/中非空的真实反馈/作答证据文件")
    records = editions(root, args.date + timedelta(days=1))
    known = {item["lesson"]["unit_id"] for item in records} | {item["exercise"]["id"] for item in records}
    if args.id not in known:
        raise ValueError("反馈对象必须是已经生成的单元或题目")
    path = local(root) / "progress.json"
    state = read_json(path, {"schema_version": 1, "units": {}})
    old = state["units"].get(args.id, {})
    if old and args.date < date.fromisoformat(old["date"]):
        raise ValueError("不能用早期反馈覆盖后来的状态")
    if args.level != "read" and args.result is None:
        raise ValueError("实际作答需要评价wrong/partial/correct")
    if args.level == "read" and args.result is not None:
        raise ValueError("已读确认不等于作答或复习评价")
    if args.level == "mastered" and (old.get("level") not in ("practiced", "mastered")
                                    or old.get("review_index", 0) < 3 or args.result != "correct"):
        raise ValueError("掌握标记需要此前实践、至少完成第7天复习及当前正确性评价")
    item = dict(old)
    item.update(date=args.date.isoformat(), evidence=str(evidence.relative_to(root)))
    # A later reading confirmation must not erase demonstrated practice.
    item["level"] = max((old.get("level", "read"), args.level), key=lambda value: LEVELS[value])
    if args.result in ("wrong", "partial"):
        item.update(level="practiced", review_anchor=args.date.isoformat(), review_index=0)
    elif args.result == "correct":
        if not old.get("review_anchor"):
            item.update(review_anchor=args.date.isoformat(), review_index=0)
        elif old.get("next_review") and args.date >= date.fromisoformat(old["next_review"]):
            item["review_index"] = min(old["review_index"] + 1, len(INTERVALS))
    if item.get("review_anchor"):
        index = item["review_index"]
        item["next_review"] = ((date.fromisoformat(item["review_anchor"]) + timedelta(days=INTERVALS[index])).isoformat()
                               if index < len(INTERVALS) else None)
    state["units"][args.id] = item
    # Preserve feedback events for actual weekly review; do not export private text.
    log = local(root) / "feedback.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"id": args.id, "level": args.level, "result": args.result,
                                 "date": args.date.isoformat(), "evidence": item["evidence"]}, ensure_ascii=False) + "\n")
    write_json(path, state)
    return {"id": args.id, **item}


def git(path: Path, *arguments: str, transport: str = "https") -> str:
    options = ["-c", "http.lowSpeedLimit=1", "-c", "http.lowSpeedTime=60"]
    if transport == "ssh":
        options += ["-c", "url.git@github.com:.insteadOf=https://github.com/"]
    result = subprocess.run(["git", *options, "-C", str(path), *arguments],
                            text=True, capture_output=True, timeout=600, check=False)
    if result.returncode:
        raise ValueError(result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def sources(root: Path, action: str, selected: str | None,
            transport: str = "https") -> list[dict[str, Any]]:
    configs = read_json(root / "docs/daily/sources.json")["repositories"]
    if selected and selected not in {item["id"] for item in configs}:
        raise ValueError(f"未知源码仓库: {selected}")
    def source(config: dict[str, Any]) -> dict[str, Any]:
        path = local(root) / "sources" / config["id"]
        def run(*arguments: str) -> str:
            return git(path, *arguments, transport=transport)
        if action == "init" and not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            git(path.parent, "clone", "--depth", "1", "--filter=" + config.get("filter", "blob:none"), "--no-checkout",
                "--branch", config["branch"], config["url"], str(path), transport=transport)
        if not (path / ".git").exists():
            raise ValueError(f"镜像尚未克隆: {config['id']}")
        if run("config", "--get", "remote.origin.url") != config["url"]:
            raise ValueError("镜像origin与来源配置不同")
        before = run("rev-parse", "HEAD")
        changes = []
        if action == "init":
            # Recover an interrupted initial checkout, but preserve real edits.
            initial_checkout = not any(child.name != ".git" for child in path.iterdir())
            if not initial_checkout and (path / ".git/index").exists() and run("status", "--porcelain"):
                raise ValueError(f"镜像有本地修改，不自动覆盖: {config['id']}")
            patterns = (["--no-cone", *["/" + value for value in config["sparse"]]]
                        if config.get("sparse_mode") == "no-cone" else ["--cone", *config["sparse"]])
            run("sparse-checkout", "set", *patterns)
            if initial_checkout:
                # Populate an empty index using sparse checkout's read-tree mechanism.
                run("read-tree", "-mu", "HEAD")
        if action == "update":
            if run("status", "--porcelain"):
                raise ValueError(f"镜像有本地修改，不自动覆盖: {config['id']}")
            run("fetch", "--depth=32", "--filter=" + config.get("filter", "blob:none"), "origin", config["branch"])
            after = run("rev-parse", "FETCH_HEAD")
            changes = run("diff", "--name-only", before, after, "--", *config["sparse"]).splitlines()
            # This is an owned, clean reading mirror; move its ref and materialize
            # only the selected paths without invoking checkout hooks.
            run("update-ref", "HEAD", after)
            run("read-tree", "-mu", after)
        if action != "snapshot":
            run("sparse-checkout", "reapply")
        missing = [value for value in config["sparse"] if not (path / value).exists()]
        if missing:
            raise ValueError(f"sparse源码未完整取得: {config['id']}: {missing}; 可重试sparse-checkout reapply")
        return {"id": config["id"], "status": "ready", "path": str(path.relative_to(root)),
                       "sha": run("rev-parse", "HEAD"), "previous_sha": before,
                       "commit_time": run("show", "-s", "--format=%cI", "HEAD"),
                       "observed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
                       "shallow": run("rev-parse", "--is-shallow-repository") == "true",
                       "worktree_clean": not bool(run("status", "--porcelain")),
                       "changed_files": changes}
    output = []
    for config in configs:
        if selected and config["id"] != selected:
            continue
        try:
            output.append(source(config))
        except (ValueError, OSError, subprocess.TimeoutExpired) as error:
            output.append({"id": config["id"], "status": "unavailable", "error": str(error)})
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    commands = parser.add_subparsers(dest="command", required=True)
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    for name in ("history", "plan"):
        sub = commands.add_parser(name)
        sub.add_argument("--date", type=date.fromisoformat, default=today)
    sub = commands.add_parser("check")
    sub.add_argument("manifest", type=Path)
    sub = commands.add_parser("sources")
    sub.add_argument("action", choices=("init", "update", "snapshot"))
    sub.add_argument("--repo")
    sub.add_argument("--transport", choices=("https", "ssh"), default="https")
    sub = commands.add_parser("feedback")
    sub.add_argument("--id", required=True)
    sub.add_argument("--level", choices=tuple(LEVELS), required=True)
    sub.add_argument("--result", choices=("wrong", "partial", "correct"))
    sub.add_argument("--date", type=date.fromisoformat, default=today)
    sub.add_argument("--evidence", required=True)
    args = parser.parse_args()
    try:
        root = args.root.resolve()
        if args.command == "history":
            result = history(root, args.date)
        elif args.command == "plan":
            result = plan(root, args.date)
        elif args.command == "check":
            result = check(root, root / args.manifest)
        elif args.command == "feedback":
            result = feedback(root, args)
        else:
            result = sources(root, args.action, args.repo, args.transport)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if args.command == "sources" and any(item["status"] != "ready" for item in result) else 0
    except (ValueError, KeyError, TypeError, OSError, subprocess.TimeoutExpired) as error:
        print(f"错误: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
