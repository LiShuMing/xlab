from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

from tech_radar.domain import PublishResult, Signal


def _clean(value: str) -> str:
    return " ".join(value.replace("|", "\\|").split())


def _signal_link(signal: Signal, label: str) -> str:
    """Render links only for records collected from a real source."""
    if not signal.url or "demo" in signal.tags:
        return label
    return f"[{label}]({signal.url})"


def _edition_path(directory: Path, local_date: str, suffix: str) -> Path:
    base = directory / f"{local_date}{suffix}"
    if not base.exists():
        return base
    edition = 2
    while True:
        candidate = directory / f"{local_date}-{edition:02d}{suffix}"
        if not candidate.exists():
            return candidate
        edition += 1


class MarkdownPublisher:
    def __init__(
        self,
        publisher_id: str,
        directory: Path,
        limit: int = 100,
        curated_threshold: int = 100,
        priority_read_limit: int = 15,
        writing_candidate_limit: int = 30,
        topic_candidate_limit: int = 10,
        people_limit: int = 20,
        max_top_picks_per_author: int = 2,
        max_top_picks_per_topic: int = 6,
    ) -> None:
        self.publisher_id = publisher_id
        self.directory = directory
        self.limit = limit
        self.curated_threshold = curated_threshold
        self.priority_read_limit = priority_read_limit
        self.writing_candidate_limit = writing_candidate_limit
        self.topic_candidate_limit = topic_candidate_limit
        self.people_limit = people_limit
        self.max_top_picks_per_author = max_top_picks_per_author
        self.max_top_picks_per_topic = max_top_picks_per_topic

    def publish(
        self, signals: Sequence[Signal], *, local_date: str
    ) -> PublishResult:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = _edition_path(self.directory, local_date, ".md")
        selected = list(signals[: self.limit])
        curated = [
            signal for signal in selected if signal.priority >= self.curated_threshold
        ]
        supplemental = [
            signal for signal in selected if signal.priority < self.curated_threshold
        ]

        lines = [
            f"# Tech Radar — {local_date}",
            "",
            (
                f"> 共收录 {len(selected)} 条：个人精选 {len(curated)} 条，"
                f"补充观察 {len(supplemental)} 条；各区按评分降序排列。"
            ),
            "",
        ]
        demo_count = sum("demo" in signal.tags for signal in selected)
        if demo_count:
            lines.extend(
                (
                    (
                        f"> ⚠️ 离线结构预览：其中 {demo_count} 条为模拟数据，"
                        "不代表真实 X/Reddit 词条，已禁用原文链接。"
                    ),
                    "",
                )
            )
        if selected:
            self._append_overview(lines, selected)
        if curated:
            lines.extend(("## 个人精选", ""))
            self._append_grouped(lines, curated)
        if supplemental:
            lines.extend(("## 补充观察", ""))
            self._append_grouped(lines, supplemental)
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        return PublishResult(
            self.publisher_id,
            str(path),
            len(selected),
            tuple((signal.platform, signal.external_id) for signal in selected),
        )

    def _append_overview(
        self, lines: list[str], signals: Sequence[Signal]
    ) -> None:
        topic_counts: dict[str, int] = defaultdict(int)
        for signal in signals:
            topic = str(signal.annotations.get("topic", "未分类"))
            topic_counts[topic] += 1
        topic_summary = "；".join(
            f"{topic} {count} 条"
            for topic, count in sorted(
                topic_counts.items(), key=lambda item: (-item[1], item[0])
            )
        )
        lines.extend(("## 今日概览", "", f"- 主题分布：{topic_summary}", ""))

        top_picks = self._select_diverse(signals, self.priority_read_limit)
        lines.extend(("## 今日 Top Picks", ""))
        for index, signal in enumerate(
            top_picks, start=1
        ):
            summary = _clean(
                str(
                    signal.annotations.get("summary_zh")
                    or signal.content
                    or signal.title
                )
            )
            link = _signal_link(signal, summary)
            lines.append(f"{index}. {link}")
            why = _clean(str(signal.annotations.get("why_it_matters", "")))
            if why:
                lines.append(f"   - 价值判断：{why}")
        lines.append("")

        self._append_topic_candidates(lines, signals)
        self._append_people(lines, signals)

        candidate_pool = [
            signal
            for signal in signals
            if signal.annotations.get("writing_angle")
        ]
        candidates = self._select_diverse(
            candidate_pool,
            self.writing_candidate_limit,
            per_author=max(3, self.max_top_picks_per_author),
            per_topic=max(10, self.max_top_picks_per_topic),
        )
        if candidates:
            lines.extend(("## 可写作选题", ""))
            for signal in candidates:
                title = _clean(signal.title or signal.content or signal.external_id)
                angle = _clean(str(signal.annotations["writing_angle"]))
                lines.append(f"- **{title}**：{angle}")
            lines.append("")

    def _select_diverse(
        self,
        signals: Sequence[Signal],
        limit: int,
        *,
        per_author: int | None = None,
        per_topic: int | None = None,
    ) -> list[Signal]:
        author_limit = per_author or self.max_top_picks_per_author
        topic_limit = per_topic or self.max_top_picks_per_topic
        selected: list[Signal] = []
        selected_keys: set[tuple[str, str]] = set()
        author_counts: dict[str, int] = defaultdict(int)
        topic_counts: dict[str, int] = defaultdict(int)
        for signal in signals:
            author = signal.author.casefold()
            topic = str(signal.annotations.get("topic", "未分类"))
            if author_counts[author] >= author_limit:
                continue
            if topic_counts[topic] >= topic_limit:
                continue
            selected.append(signal)
            selected_keys.add((signal.platform, signal.external_id))
            author_counts[author] += 1
            topic_counts[topic] += 1
            if len(selected) >= limit:
                return selected
        for signal in signals:
            key = (signal.platform, signal.external_id)
            if key in selected_keys:
                continue
            selected.append(signal)
            if len(selected) >= limit:
                break
        return selected

    def _append_topic_candidates(
        self, lines: list[str], signals: Sequence[Signal]
    ) -> None:
        groups: dict[str, list[Signal]] = defaultdict(list)
        for signal in signals:
            topic = str(signal.annotations.get("topic", "未分类"))
            groups[topic].append(signal)
        ranked_groups = sorted(
            groups.items(), key=lambda item: (-item[1][0].score, item[0])
        )
        lines.extend(("## 主题候选池", ""))
        for topic, items in ranked_groups:
            lines.extend((f"### {topic}", ""))
            for signal in self._select_diverse(
                items,
                self.topic_candidate_limit,
                per_author=2,
                per_topic=self.topic_candidate_limit,
            ):
                title = _clean(signal.title or signal.content or signal.external_id)
                link = _signal_link(signal, title)
                relevance = signal.annotations.get("relevance", "-")
                lines.append(
                    f"- {link} — {signal.author} · 相关度 {relevance}/100"
                )
            lines.append("")

    def _append_people(
        self, lines: list[str], signals: Sequence[Signal]
    ) -> None:
        people: dict[str, dict[str, object]] = {}
        for signal in signals:
            author = signal.author.strip()
            if not author or author == "unknown" or author.startswith("r/"):
                continue
            key = author.casefold()
            record = people.setdefault(
                key,
                {
                    "author": author,
                    "platform": signal.platform,
                    "count": 0,
                    "score": 0.0,
                    "topics": set(),
                },
            )
            record["count"] = int(record["count"]) + 1
            record["score"] = max(float(record["score"]), signal.score)
            topics = record["topics"]
            if isinstance(topics, set):
                topics.add(str(signal.annotations.get("topic", "未分类")))
        ranked = sorted(
            people.values(),
            key=lambda item: (-float(item["score"]), -int(item["count"])),
        )[: self.people_limit]
        if not ranked:
            return
        lines.extend(("## 值得持续关注的人", ""))
        for record in ranked:
            author = str(record["author"])
            platform = str(record["platform"])
            if platform == "twitter":
                display = f"[@{author}](https://x.com/{author.lstrip('@')})"
            elif platform == "reddit":
                display = f"[u/{author}](https://www.reddit.com/user/{author})"
            else:
                display = author
            topics = record["topics"]
            topic_text = "、".join(sorted(topics)) if isinstance(topics, set) else ""
            lines.append(
                f"- {display}：候选 {record['count']} 条；主题 {topic_text}"
            )
        lines.append("")

    @staticmethod
    def _append_grouped(lines: list[str], signals: Sequence[Signal]) -> None:
        groups: dict[str, list[Signal]] = defaultdict(list)
        for signal in signals:
            groups[signal.platform].append(signal)
        for platform in sorted(groups):
            lines.extend((f"### {platform}", ""))
            for signal in groups[platform]:
                label = _clean(signal.title or signal.content or signal.external_id)
                heading = f"#### {_signal_link(signal, label)}"
                lines.extend(
                    (
                        heading,
                        "",
                        f"- 来源：{signal.source_id} / {signal.author}",
                        f"- 优先级：{signal.priority}",
                        f"- 评分：{signal.score:.2f}",
                        f"- 标签：{', '.join(signal.tags) or '-'}",
                    )
                )
                if signal.metrics:
                    metrics = ", ".join(
                        f"{key}={value}" for key, value in signal.metrics.items()
                    )
                    lines.append(f"- 指标：{metrics}")
                if signal.published_at:
                    lines.append(f"- 发布时间：{signal.published_at}")
                topic = _clean(str(signal.annotations.get("topic", "")))
                if topic:
                    lines.append(f"- 主题：{topic}")
                relevance = signal.annotations.get("relevance")
                if relevance is not None:
                    lines.append(f"- 相关度：{relevance}/100")
                summary = _clean(
                    str(signal.annotations.get("summary_zh") or signal.content)
                )
                if summary and summary != label:
                    lines.extend(("", f"**摘要**：{summary[:600]}"))
                why = _clean(str(signal.annotations.get("why_it_matters", "")))
                if why:
                    lines.extend(("", f"**为什么值得关注**：{why}"))
                angle = _clean(str(signal.annotations.get("writing_angle", "")))
                if angle:
                    lines.extend(("", f"**可写角度**：{angle}"))
                lines.append("")


class JsonlPublisher:
    def __init__(self, publisher_id: str, directory: Path, limit: int = 1000) -> None:
        self.publisher_id = publisher_id
        self.directory = directory
        self.limit = limit

    def publish(
        self, signals: Sequence[Signal], *, local_date: str
    ) -> PublishResult:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = _edition_path(self.directory, local_date, ".jsonl")
        selected = list(signals[: self.limit])
        with path.open("w", encoding="utf-8") as stream:
            for signal in selected:
                record = {
                    field: getattr(signal, field)
                    for field in signal.__dataclass_fields__
                }
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        return PublishResult(
            self.publisher_id,
            str(path),
            len(selected),
            tuple((signal.platform, signal.external_id) for signal in selected),
        )


def create_markdown_publisher(
    publisher_id: str, options: dict[str, object]
) -> MarkdownPublisher:
    return MarkdownPublisher(
        publisher_id,
        Path(str(options.get("directory", "output"))),
        int(options.get("limit", 100)),
        int(options.get("curated_threshold", 100)),
        int(options.get("priority_read_limit", 15)),
        int(options.get("writing_candidate_limit", 30)),
        int(options.get("topic_candidate_limit", 10)),
        int(options.get("people_limit", 20)),
        int(options.get("max_top_picks_per_author", 2)),
        int(options.get("max_top_picks_per_topic", 6)),
    )


def create_jsonl_publisher(
    publisher_id: str, options: dict[str, object]
) -> JsonlPublisher:
    return JsonlPublisher(
        publisher_id,
        Path(str(options.get("directory", "output"))),
        int(options.get("limit", 1000)),
    )
