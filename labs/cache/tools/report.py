"""Self-contained cache-policy report; measured hit rates and policy costs stay separate."""

from collections import defaultdict
import html
import json
from pathlib import Path
import statistics

LAB = Path(__file__).resolve().parents[1]
FIELDS = (
    "workload",
    "capacity",
    "algorithm",
    "window_percent",
    "protected_percent",
    "aging_factor",
)
COLORS = {
    "fifo": "#7d6e58",
    "lru": "#112f41",
    "lfu": "#956218",
    "slru": "#11666b",
    "wtinylfu": "#8266a5",
    "arc": "#b74c52",
    "reference-lru": "#758a95",
}
ALGORITHMS = [
    (
        "FIFO",
        "按进入先后淘汰；命中不调整顺序",
        "低维护成本",
        "不识别热度；可能发生容量更大反而更多缺失",
    ),
    (
        "LRU",
        "Least Recently Used，淘汰最近最少访问的条目",
        "适应时间局部性、热点迁移快",
        "大扫描会把旧热点逐出",
    ),
    (
        "LFU",
        "Least Frequently Used，淘汰驻留期访问次数最少的条目；同频按 LRU",
        "稳定长期热点",
        "本实现不衰减，旧热点可能长期占用容量；有序频率桶并非严格 O(1)",
    ),
    (
        "SLRU",
        "Segmented LRU：试用区 + 保护区，试用区命中后晋升",
        "一次性扫描主要消耗试用区；不维护频率草图",
        "固定分区；再次访问间隔太长的新条目可能来不及晋升",
    ),
    (
        "W-TinyLFU",
        "小 LRU 窗口 + 主 SLRU；草图比较窗口候选与主区受害者频率",
        "兼顾新条目与长期热度，通常能抵御单次扫描",
        "历史频率、窗口和衰减影响适应速度；估计碰撞和批量衰减有额外成本",
    ),
    (
        "ARC",
        "Adaptive Replacement Cache：近期/重复访问区 + 两个仅保存键的历史区",
        "利用历史命中调整近期区目标，无需固定冷热分界",
        "更多链表与历史键；不是零成本自动调优",
    ),
]


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def variant(job: dict) -> str:
    if job["algorithm"] == "wtinylfu":
        return f"wtinylfu w{job['window_percent']}% p{job['protected_percent']}% a{job['aging_factor']}C"
    if job["algorithm"] == "slru":
        return f"slru p{job['protected_percent']}%"
    return job["algorithm"]


def default(job: dict) -> bool:
    return (job["window_percent"], job["protected_percent"], job["aging_factor"]) == (1, 80, 10)


def summarize(jobs: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for job in jobs:
        groups[tuple(job[key] for key in FIELDS)].append(job)
    result = []
    for key, records in groups.items():
        row = dict(zip(FIELDS, key))
        samples = [sample for job in records for sample in job["samples"]]
        times = [sample["ns_per_op"] for sample in samples]
        points = sum(w["points"] for job in records for w in job["windows"])
        point_hits = sum(w["point_hits"] for job in records for w in job["windows"])
        scans = sum(w["scans"] for job in records for w in job["windows"])
        scan_hits = sum(w["scan_hits"] for job in records for w in job["windows"])
        total = sum(job["count"] for job in records)
        row.update(
            variant=variant(row),
            median=statistics.median(times),
            cpu=statistics.median(s["cpu_ns_per_op"] for s in samples),
            minimum=min(times),
            maximum=max(times),
            sample_count=len(samples),
            seeds=len(records),
            hit_rate=sum(job["hits"] for job in records) / total,
            point_hit=point_hits / points if points else None,
            scan_hit=scan_hits / scans if scans else None,
            p50=statistics.median(j["latency"]["all"]["p50"] for j in records),
            p95=statistics.median(j["latency"]["all"]["p95"] for j in records),
            p99=statistics.median(j["latency"]["all"]["p99"] for j in records),
            clock_floor=statistics.median(j["clock_floor"]["p50"] for j in records),
            sketch_bytes=records[0]["windows"][-1]["layout"]["sketch_bytes"],
            history=statistics.median(j["windows"][-1]["layout"]["history"] for j in records),
            records=records,
        )
        row["spread_pct"] = (row["maximum"] - row["minimum"]) / row["median"] * 100
        row["events"] = {
            name: statistics.median(
                sum(w["events"][name] for w in job["windows"]) for job in records
            )
            for name in records[0]["windows"][0]["events"]
        }
        result.append(row)
    baselines = {(r["workload"], r["capacity"]): r for r in result if r["algorithm"] == "lru"}
    for row in result:
        baseline = baselines.get((row["workload"], row["capacity"]))
        row["baseline_ns"] = baseline["median"] if baseline else None
        row["delta_ns"] = row["median"] - baseline["median"] if baseline else None
        row["delta_pct"] = (row["median"] / baseline["median"] - 1) * 100 if baseline else None
        row["hit_delta_pp"] = (row["hit_rate"] - baseline["hit_rate"]) * 100 if baseline else None
    return sorted(
        result, key=lambda row: (row["workload"], row["capacity"], row["algorithm"], row["variant"])
    )


def rate(value: float | None) -> str:
    return "不适用" if value is None else f"{value * 100:.2f}%"


def curves(rows: list[dict]) -> str:
    parts = [
        "<section><h2>点查命中率随请求推进</h2><p>容量 512 条目，默认参数；"
        "同一窗口跨种子按点查请求数加权。冷启动计入；扫描请求不计入点查分母。"
        "每个灰色分隔线代表完整轨迹的四分之一。</p>"
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,480px),1fr));gap:14px">'
    ]
    for workload in ("scan_mix", "hot_shift", "recency_bursts", "interleaved"):
        selected = [
            r
            for r in rows
            if r["workload"] == workload
            and r["capacity"] == 512
            and default(r)
            and r["algorithm"] != "reference-lru"
        ]
        if not selected:
            continue
        parts.append(
            f'<div class="card"><h3>{escape(workload)}</h3><svg viewBox="0 0 600 255" '
            'role="img" aria-label="分窗口点查命中率" style="width:100%;height:auto">'
            '<path d="M45 15V190H575" stroke="#aab8bf" fill="none"/>'
            '<text x="3" y="20" font-size="11">100%</text><text x="15" y="194" font-size="11">0%</text>'
        )
        for x in (177.5, 310, 442.5):
            parts.append(f'<path d="M{x} 15V190" stroke="#dce5ed" stroke-dasharray="3 3"/>')
        for row in selected:
            records = row["records"]
            count = records[0]["count"]
            segments = []
            for index in range(len(records[0]["windows"])):
                windows = [j["windows"][index] for j in records]
                points = sum(w["points"] for w in windows)
                if not points:
                    if segments:
                        parts.append(
                            f'<polyline points="{" ".join(segments)}" fill="none" '
                            f'stroke="{COLORS[row["algorithm"]]}" stroke-width="1.8"/>'
                        )
                        segments = []
                    continue
                hit_rate = sum(w["point_hits"] for w in windows) / points
                x = 45 + windows[0]["end"] / count * 530
                y = 190 - hit_rate * 175
                segments.append(f"{x:.2f},{y:.2f}")
                parts.append(
                    f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2" fill="{COLORS[row["algorithm"]]}">'
                    f"<title>{escape(row['algorithm'])} 请求 {windows[0]['end']}: {hit_rate * 100:.2f}%</title></circle>"
                )
            if segments:
                parts.append(
                    f'<polyline points="{" ".join(segments)}" fill="none" '
                    f'stroke="{COLORS[row["algorithm"]]}" stroke-width="1.8"/>'
                )
        parts.append(
            '<text x="45" y="209" font-size="11">开始</text><text x="530" y="209" font-size="11">轨迹结束</text>'
        )
        for index, row in enumerate(selected):
            parts.append(
                f'<text x="{index * 98}" y="238" font-size="11" '
                f'fill="{COLORS[row["algorithm"]]}">{escape(row["algorithm"])}</text>'
            )
        parts.append("</svg></div>")
    return "".join(parts) + "</div></section>"


def render(manifest: dict, jobs: list[dict]) -> tuple[str, list[dict]]:
    rows = summarize(jobs)
    parts = [
        '<nav><a href="#overview">结论与边界</a><a href="#algorithms">算法区别</a>'
        '<a href="#measurements">实测对照</a><a href="#policy-choice">策略取舍</a>'
        '<a href="#evidence">原始证据</a></nav><section id="overview"><h2>淘汰、准入与混合负载</h2><div class="cards">'
    ]
    for number, label in [
        (len(rows), "组策略/参数对照"),
        (sum(r["sample_count"] for r in rows), "批量计时样本"),
        (len(jobs), "同轨迹工作进程"),
        (manifest.get("failed_jobs", 0), "执行失败"),
    ]:
        parts.append(
            f'<div class="card"><strong>{escape(number)}</strong><span>{label}</span></div>'
        )
    parts.append(
        "</div><p>每种策略重放同一条预先生成的只读轨迹，缺失后立即读取并尝试缓存。"
        "容量按等大条目数比较；4 KiB/块仅用于解释载荷预算，实验没有分配块内容或执行磁盘/网络 I/O。"
        "所有策略没有获知请求属于扫描还是点查，标签仅用于统计。</p>"
    )
    observations = []
    for workload in ("scan_mix", "hot_shift", "recency_bursts"):
        group = {
            r["algorithm"]: r
            for r in rows
            if r["workload"] == workload and r["capacity"] == 512 and default(r)
        }
        if "slru" in group and "wtinylfu" in group:
            slru, tiny = group["slru"], group["wtinylfu"]
            observations.append(
                f"<li>{escape(workload)} / C=512：SLRU 点查命中 {rate(slru['point_hit'])}，"
                f"W-TinyLFU {rate(tiny['point_hit'])}；策略平均墙钟耗时 "
                f"{slru['median']:.2f} / {tiny['median']:.2f} ns/请求。</li>"
            )
    parts.append("<ul>" + "".join(observations) + "</ul>")
    noisy = sum(r["spread_pct"] > 20 for r in rows)
    parts.append(
        f'<div class="notice">{noisy}/{len(rows)} 组批量样本范围超过中位数的 20%。'
        "共享主机上耗时会波动；命中率来自确定性请求重放，与计时波动分别分析。"
        "这不是数据库或 CacheSystem 整体性能测试。</div>"
        "<p>批量 ns/请求包含缓存创建、完整重放、销毁及命中摘要计算；不逐请求读时钟。"
        "P50/P95/P99 来自另一轮逐请求墙钟测量，仅覆盖缓存策略 Access，包含时钟测量影响；"
        "表中为每个种子分位数的中位数，不是合并分布的分位数。不能解释为数据库查询或 I/O 延迟。"
        "记录空时钟对开销供比较，不做可能产生负数的扣减。</p></section>"
    )
    parts.append(
        '<section id="algorithms"><h2>算法异同</h2><div class="table-scroll"><table><thead><tr>'
        "<th>策略</th><th>规则</th><th>长处</th><th>代价与失效场景</th></tr></thead><tbody>"
    )
    for algorithm in ALGORITHMS:
        parts.append("<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in algorithm) + "</tr>")
    parts.append(
        "</tbody></table></div><p>淘汰决定谁离开，准入决定谁值得留下。SLRU 通过再次命中晋升，"
        "W-TinyLFU 再增加历史频率准入；两者都不是简单的全缓存 LRU。"
        "本实验 W-TinyLFU 为固定窗口、4 行 4 位计数草图、平频拒绝、按请求数周期减半；"
        "没有 doorkeeper、自动窗口调节或生产并发优化。</p>"
        "<p>reference-lru 使用本仓库内 CacheSystem 风格的 LruCache：mutex、shared_ptr/weak_ptr 链表和值检查；"
        "与实验 LRU 的命中序列必须一致，耗时属于实现对照，不能只归因于淘汰算法。"
        "CacheSystem 的 ARC 变体双部件容量与晋升方式不同，未混作标准 ARC 成绩。</p></section>"
    )
    parts.append(curves(rows))
    parts.append(
        '<section id="measurements" data-report-explorer><h2>命中率、策略成本与元数据</h2>'
        "<p>时间和命中率都对照相同负载/容量的实验 LRU；命中差单位为百分点。"
        "W 是窗口占总容量比例；P 是保护区占主区比例；A 是草图衰减请求间隔的容量倍数。</p>"
        '<div class="controls"><label>搜索<input data-report-search placeholder="负载 / 参数"></label>'
    )
    for field, label in [("workload", "负载"), ("algorithm", "算法"), ("capacity", "容量条目")]:
        parts.append(
            f'<label>{label}<select data-report-filter="{field}"><option value="all">全部</option>'
        )
        parts.extend(
            f'<option value="{escape(v)}">{escape(v)}</option>'
            for v in sorted({r[field] for r in rows})
        )
        parts.append("</select></label>")
    parts.append(
        '<label>排序<select data-report-sort><option value="">默认</option>'
        '<option value="hit:desc">命中率降序</option><option value="ns:asc">耗时升序</option>'
        '<option value="delta:desc">耗时退化优先</option><option value="spread:desc">波动优先</option>'
        "</select></label><button data-report-reset>重置</button><span data-report-count></span></div>"
        '<div class="table-scroll index"><table data-report-table><thead><tr>'
    )
    columns = [
        "明细",
        "负载 / 容量",
        "策略 / 参数",
        "整体 / 点查 / 扫描命中率",
        "相对 LRU 命中差 pp",
        "LRU / 当前墙钟 ns/请求",
        "耗时差 ns / %",
        "当前 CPU ns/请求",
        "策略 P50/P95/P99 ns",
        "空时钟 P50 ns",
        "样本 min～max / 波动 %",
        "淘汰 / 准入拒绝",
        "晋升 / 降级 / 衰减",
        "历史键 / 草图 B",
        "样本 / 种子",
    ]
    parts.extend(f"<th>{c}</th>" for c in columns)
    parts.append("</tr></thead><tbody>")
    for index, row in enumerate(rows):
        delta = row["delta_pct"] if row["delta_pct"] is not None else ""
        parts.append(
            f'<tr data-workload="{escape(row["workload"])}" data-algorithm="{escape(row["algorithm"])}" '
            f'data-capacity="{row["capacity"]}" data-ns="{row["median"]}" data-delta="{delta}" '
            f'data-hit="{row["hit_rate"]}" data-spread="{row["spread_pct"]}">'
        )
        baseline = "未测" if row["baseline_ns"] is None else f"{row['baseline_ns']:.2f}"
        time_delta = (
            "不可计算"
            if row["delta_ns"] is None
            else f"{row['delta_ns']:+.2f} / {row['delta_pct']:+.1f}%"
        )
        hit_delta = "未测" if row["hit_delta_pp"] is None else f"{row['hit_delta_pp']:+.2f}"
        events = row["events"]
        cells = [
            f'<a href="#detail-{index}">{index + 1}</a>',
            f"{escape(row['workload'])} / {row['capacity']}",
            escape(row["variant"]),
            f"{rate(row['hit_rate'])} / {rate(row['point_hit'])} / {rate(row['scan_hit'])}",
            hit_delta,
            f"{baseline} / <strong>{row['median']:.2f}</strong>",
            time_delta,
            f"{row['cpu']:.2f}",
            f"{row['p50']:.0f} / {row['p95']:.0f} / {row['p99']:.0f}",
            f"{row['clock_floor']:.0f}",
            f"{row['minimum']:.2f}～{row['maximum']:.2f} / {row['spread_pct']:.1f}%",
            f"{events['evictions']:.0f} / {events['rejections']:.0f}",
            f"{events['promotions']:.0f} / {events['demotions']:.0f} / {events['sketch_resets']:.0f}",
            f"{row['history']:.0f} / {row['sketch_bytes']}",
            f"{row['sample_count']} / {row['seeds']}",
        ]
        parts.extend(f"<td>{cell}</td>" for cell in cells)
        parts.append("</tr>")
    parts.append(
        "</tbody></table></div><p>容量是驻留条目总上限；ARC 历史区仅保存键，不保存块；"
        "草图字节是实际计数数组大小。历史键数量和草图字节不是完整元数据内存，"
        "未统计哈希桶、链表、分配器开销或进程 RSS；不声称相同总内存预算。"
        "拒绝指窗口候选未进入主区，候选此前可能已在窗口驻留。淘汰包含候选离开窗口后被拒绝。"
        "事件数按每条完整轨迹统计，再跨种子取中位数。</p></section>"
    )
    parts.append(
        '<section id="policy-choice"><h2>混合负载下的 W-TinyLFU 与 SLRU</h2>'
        "<p>下述是机制假设与本地实验，只适用于明确的实现与输入，"
        "不描述具体产品的策略变更。</p>"
        "<ol><li>长扫描与新点查热点同时到来时，旧频率可能继续保护旧热点，"
        "使近期会复用的新块在获得足够频率前被拒绝；SLRU 通过试用区的再次访问直接晋升。"
        "hot_shift 和 recency_bursts 用于观察该取舍。</li>"
        "<li>W-TinyLFU 的窗口若小于两次复用之间的工作集，短期复用可能得不到窗口保护；"
        "窗口比例、平频决策、草图碰撞与衰减周期都影响结果。本报告通过参数对照验证敏感性。</li>"
        "<li>频率估计和周期衰减增加每次访问及部分操作的成本；更简单的链表维护可能让策略耗时更平稳。"
        "单线程本地耗时只能检查本实现，不能证明生产锁竞争或 I/O 尾延迟的原因。</li></ol>"
        "<p>单次扫描通常正是 TinyLFU 擅长过滤的负载；不能推导出 SLRU 普遍更抗扫描。"
        "实现参数、分片、块大小、读放大、扫描是否绕过缓存、并发和固定内存预算也可能改变结论。"
        "升级应分别观察点查/扫描命中、分片与容量、后端读取量、缓存策略 CPU 和查询 P95/P99，"
        "并用相同流量/预热条件重建基线。这里没有运行真实数据库，也没有测查询端到端延迟。</p></section>"
    )
    parts.append(
        '<section id="evidence"><h2>原始证据与复现</h2><p><a href="samples.csv">批量样本 CSV</a> · '
        '<a href="windows.csv">逐窗口 CSV</a> · <a href="jobs.jsonl">逐种子分位数/直方图/事件</a> · '
        '<a href="summary.json">汇总 JSON</a> · <a href="manifest.json">源码与二进制摘要</a> · '
        '<a href="tests.log">测试日志</a> · <a href="build.log">构建日志</a> · '
        '<a href="events.jsonl">进度事件</a></p><details><summary>环境和运行清单</summary><pre>'
        + escape(json.dumps(manifest, ensure_ascii=False, indent=2))
        + "</pre></details></section>"
    )
    for index, row in enumerate(rows):
        parts.append(
            f'<article class="report-item" id="detail-{index}"><details><summary>{index + 1} · '
            f"{escape(row['workload'])} / C={row['capacity']} / {escape(row['variant'])}</summary>"
            '<div class="detail-body"><p>逐种子摘要；完整窗口、操作耗时直方图及命中摘要见 jobs.jsonl。</p><pre>'
        )
        details = []
        for job in row["records"]:
            details.append(
                {
                    k: job[k]
                    for k in (
                        "seed",
                        "trace_hash",
                        "hit_digest",
                        "hits",
                        "latency",
                        "phase_latency",
                        "clock_floor",
                        "samples",
                    )
                }
            )
        parts.append(
            escape(json.dumps(details, ensure_ascii=False, indent=2))
            + "</pre></div></details></article>"
        )
    title = "Cache 淘汰与准入策略：混合负载实测"
    subtitle = escape(
        f"{manifest.get('started_at', '')} · {manifest.get('suite', '')} · "
        f"CPU {manifest.get('cpu', {}).get('selected', '未绑定')} · {manifest.get('status', '')}"
    )
    css, js = (LAB / "assets/report.css").read_text(), (LAB / "assets/report.js").read_text()
    document = (
        f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta name="referrer" content="no-referrer"><title>{title}</title><style>{css}</style></head>'
        f'<body><header><div class="eyebrow">LOCAL CACHE EXPERIMENT · 实测与证据</div><h1>{title}</h1>'
        f'<p class="muted">{subtitle}</p></header><main>{"".join(parts)}</main><script>{js}</script></body></html>'
    )
    return document, rows


def generate(directory: Path, manifest: dict, jobs: list[dict]) -> Path:
    document, rows = render(manifest, jobs)
    output = directory / "report.html"
    with output.open("x") as handle:
        handle.write(document)
    clean_rows = [{k: v for k, v in row.items() if k != "records"} for row in rows]
    (directory / "summary.json").write_text(
        json.dumps(clean_rows, ensure_ascii=False, indent=2) + "\n"
    )
    return output
