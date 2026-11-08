"""Offline aggregate-state report, sharing the lab's CSS, controls and evidence format."""

import html
import json
from pathlib import Path
import statistics

LAB = Path(__file__).resolve().parents[1]


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def median(row: dict, field: str) -> float:
    return statistics.median(float(sample[field]) for sample in row["samples"])


def phase_charts(rows: list[dict]) -> str:
    parts = [
        "<section><h2>非定常输入：四阶段 CPU 耗时</h2><p>单位 ns/输入行，越低越好；"
        "每点为跨种子、跨批次的中位数。分段计时包含当段扩容和新状态创建，"
        "不含表对象创建、最终销毁和部分计时开销，因此不能直接相加得到整流耗时。</p>"
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));gap:14px">'
    ]
    colors = {
        "std": "#112f41",
        "std-eager": "#956218",
        "inline": "#8266a5",
        "arena-lazy": "#11666b",
    }
    for case in sorted({row["case_name"] for row in rows}):
        for size in sorted({row["state_bytes"] for row in rows}, key=int):
            selected = [
                row
                for row in rows
                if row["case_name"] == case
                and row["state_bytes"] == size
                and row["distribution"] == "phases"
            ]
            if not selected:
                continue
            maximum = max(
                median(row, f"phase{phase}_cpu_ns_per_op")
                for row in selected
                for phase in range(1, 5)
            )
            parts.append(
                f'<div class="card"><h3>{escape(case)} · {escape(size)} B/状态</h3>'
                '<svg viewBox="0 0 480 230" role="img" aria-label="四阶段 CPU 耗时曲线" '
                'style="width:100%;height:auto"><path d="M45 15V170H450" fill="none" stroke="#aab8bf"/>'
                f'<text x="4" y="18" font-size="11">{maximum:.1f}</text>'
                '<text x="30" y="173" font-size="11">0</text>'
            )
            for row in selected:
                points = [
                    (
                        65 + (phase - 1) * 120,
                        170 - median(row, f"phase{phase}_cpu_ns_per_op") / maximum * 145,
                    )
                    for phase in range(1, 5)
                ]
                color = colors[row["method"]]
                coords = " ".join(f"{x},{y:.2f}" for x, y in points)
                parts.append(
                    f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="2"/>'
                )
                for phase, (x, y) in enumerate(points, 1):
                    value = median(row, f"phase{phase}_cpu_ns_per_op")
                    parts.append(
                        f'<circle cx="{x}" cy="{y:.2f}" r="3" fill="{color}">'
                        f"<title>{escape(row['method'])} / 阶段{phase}: {value:.3f} ns/行</title></circle>"
                    )
            for phase, label in enumerate(["窄键域", "扩大键域", "前端热点", "尾端热点"]):
                parts.append(f'<text x="{45 + phase * 120}" y="190" font-size="11">{label}</text>')
            for index, row in enumerate(selected):
                parts.append(
                    f'<text x="{index * 120}" y="218" font-size="11" '
                    f'fill="{colors[row["method"]]}">{escape(row["method"])}</text>'
                )
            parts.append("</svg></div>")
    return "".join(parts) + "</div></section>"


def render(manifest: dict, rows: list[dict]) -> str:
    samples = sum(row["sample_count"] for row in rows)
    parts = [
        '<nav><a href="#overview">结论与边界</a><a href="#measurements">性能与内存</a>'
        '<a href="#evidence">原始证据</a></nav><section id="overview"><h2>聚合状态布局实测</h2><div class="cards">'
    ]
    for number, label in [
        (len(rows), "组对照"),
        (samples, "真实样本"),
        (len(manifest.get("jobs", [])), "工作进程"),
        (manifest.get("failed_jobs", 0), "执行失败"),
    ]:
        parts.append(
            f'<div class="card"><strong>{escape(number)}</strong><span>{label}</span></div>'
        )
    parts.append(
        "</div><p>对照 16 / 256 / 4096 字节聚合状态；16 B 保存 COUNT/SUM，"
        "更大状态还保存分桶 SUM，每行更新一个桶。不是只增大结构体的空白填充。</p>"
        "<ul><li>std：标准库 unordered_map + try_emplace，只有新分组构造状态。</li>"
        "<li>std-eager：同一标准库容器，先构造状态参数再 emplace；用于对照初始化 API。</li>"
        "<li>inline：线性探测槽内直接保存状态；扩容初始化新槽，并搬迁已有状态。</li>"
        "<li>arena-lazy：同样的哈希、负载阈值与线性探测，槽内保存状态索引；"
        "状态在 deque 中仅随新分组构造，扩容只搬迁键和索引。它是简化分离存储，不是 StarRocks 状态池。</li></ul>"
        "<p>整流耗时包含建表、查找、初始化、更新、扩容、销毁及分段计时开销，单位 ns/输入行。"
        "输入预先生成；每轮从空表重新处理输入。均匀分布也会产生新分组，unique 每行都是新分组。"
        "所有方法完整核对每个分组的 COUNT/SUM 与全部桶，并检查计时流式校验和。</p>"
        '<div class="notice">phases：窄键域 → 扩大键域 → 前 8 键热点 → 末 8 键热点。'
        "分段数据是批量平均耗时，不是单次操作 P99；不包含删除、淘汰、并发或溢写。"
        "NULL 是独立分组，普通键 0 与 NULL 区分。本报告是本地机制实验，没有运行 StarRocks。</div>"
    )
    observations = []
    for case in ("few-groups", "many-groups"):
        subset = {
            row["method"]: row
            for row in rows
            if row["case_name"] == case
            and row["state_bytes"] == "4096"
            and row["distribution"] == "phases"
        }
        if "inline" in subset and "arena-lazy" in subset:
            inline, arena = subset["inline"], subset["arena-lazy"]
            observations.append(
                f"<li>{case} / 4096 B / phases：inline {inline['median']:.2f}，"
                f"arena-lazy {arena['median']:.2f} ns/行；inline 耗时 / arena 耗时 = "
                f"{inline['median'] / arena['median']:.2f}×。"
                f"分配请求峰值 {median(inline, 'peak_map_bytes') / 1048576:.2f} → "
                f"{median(arena, 'peak_map_bytes') / 1048576:.2f} MiB。</li>"
            )
    if observations:
        parts.append("<ul>" + "".join(observations) + "</ul>")
    noisy = sum(row["spread_pct"] > 20 for row in rows)
    parts.append(
        f"<p>{noisy}/{len(rows)} 组样本范围超过中位数的 20%；共享宿主机干扰不能单独归因。"
        "墙钟与进程 CPU 耗时同时保留。算法收益需要按状态大小、分组数和分布分别判断。</p></section>"
    )
    parts.append(phase_charts(rows))
    parts.append(
        '<section id="measurements" data-report-explorer><h2>性能与内存对照</h2>'
        "<p>基线为相同输入、状态大小的 std；负差表示比基线耗时低。数值使用跨样本中位数，"
        '内存和初始化计数来自计时外的同输入诊断。</p><div class="controls">'
        '<label>搜索<input data-report-search placeholder="场景 / 实现"></label>'
    )
    for field, attr, label in [
        ("method", "method", "实现"),
        ("state_bytes", "stateBytes", "状态 B"),
        ("distribution", "distribution", "分布"),
        ("case_name", "caseName", "场景"),
    ]:
        parts.append(
            f'<label>{label}<select data-report-filter="{attr}"><option value="all">全部</option>'
        )
        parts.extend(
            f'<option value="{escape(value)}">{escape(value)}</option>'
            for value in sorted({row[field] for row in rows})
        )
        parts.append("</select></label>")
    parts.append(
        '<label>排序<select data-report-sort><option value="">默认</option><option value="ns:asc">耗时升序</option>'
        '<option value="delta:desc">退化优先</option><option value="spread:desc">波动优先</option>'
        '<option value="peak:desc">峰值内存降序</option></select></label>'
        "<button data-report-reset>重置</button><span data-report-count></span></div>"
        '<div class="table-scroll index"><table data-report-table><thead><tr>'
    )
    columns = [
        "明细",
        "场景 / 分布 / 输入行",
        "状态 B / 实际分组范围",
        "实现",
        "基线 ns/行",
        "当前墙钟 / CPU ns/行",
        "差值 ns / %",
        "样本 min～max / 波动 %",
        "存活 / 峰值 MiB",
        "申请次数 / 累计 MiB",
        "逻辑初始化 MiB",
        "状态搬迁 MiB",
        "扩容次数",
        "样本 / 种子",
    ]
    parts.extend(f"<th>{column}</th>" for column in columns)
    parts.append("</tr></thead><tbody>")
    for index, row in enumerate(rows):
        peak = median(row, "peak_map_bytes")
        delta_value = row["delta_pct"] if row["delta_pct"] is not None else ""
        parts.append(
            f'<tr data-method="{escape(row["method"])}" data-state-bytes="{escape(row["state_bytes"])}" '
            f'data-case-name="{escape(row["case_name"])}" data-distribution="{escape(row["distribution"])}" '
            f'data-ns="{row["median"]}" data-delta="{delta_value}" data-peak="{peak}" '
            f'data-spread="{row["spread_pct"]}">'
        )
        ndvs = [int(sample["ndv"]) for sample in row["samples"]]
        baseline = "未测" if row["baseline"] is None else f"{row['baseline']:.3f}"
        delta = (
            "不可计算"
            if row["delta_ns"] is None
            else f"{row['delta_ns']:+.3f} / {row['delta_pct']:+.1f}%"
        )
        direction = "" if row["delta_ns"] is None else ("up" if row["delta_ns"] > 0 else "down")
        cells = [
            f'<a href="#detail-{index}">{index + 1}</a>',
            f"{escape(row['case_name'])} / {escape(row['distribution'])} / {escape(row['n'])}",
            f"{escape(row['state_bytes'])} / {min(ndvs)}～{max(ndvs)}",
            escape(row["method"]),
            baseline,
            f"<strong>{row['median']:.3f}</strong> / {median(row, 'cpu_ns_per_op'):.3f}",
            f'<span class="{direction}">{delta}</span>',
            f"{row['minimum']:.3f}～{row['maximum']:.3f} / {row['spread_pct']:.1f}%",
            f"{median(row, 'map_bytes') / 1048576:.3f} / {peak / 1048576:.3f}",
            f"{median(row, 'allocations'):.0f} / {median(row, 'allocated_bytes') / 1048576:.3f}",
            f"{median(row, 'state_init_bytes') / 1048576:.3f}",
            f"{median(row, 'state_relocated_bytes') / 1048576:.3f}",
            f"{median(row, 'rehashes'):.0f}",
            f"{row['sample_count']} / {row['seeds']}",
        ]
        parts.extend(f"<td>{cell}</td>" for cell in cells)
        parts.append("</tr>")
    parts.append(
        "</tbody></table></div><p>存活与峰值为容器对象 + 分配器请求字节，峰值包含扩容时共存的新旧数组；"
        "不含分配器元数据、输入或校验参考状态，不是 RSS。申请次数、累计字节只统计堆请求。"
        "逻辑初始化按源码要求清零的状态大小计数；编译器可以消除或合并实际写入，未采集硬件写流量。"
        "搬迁只计状态字节，不含键、索引；std-eager 新插入时的候选复制也计入。"
        "所有诊断计数在专用实例执行，计时实例在编译期关闭计数。</p></section>"
        '<section id="evidence"><h2>环境与原始证据</h2><p><a href="samples.csv">原始 CSV</a> · '
        '<a href="summary.json">汇总 JSON</a> · <a href="manifest.json">运行清单与源码摘要</a> · '
        '<a href="tests.log">测试日志</a> · <a href="build.log">构建日志</a> · '
        '<a href="events.jsonl">进度事件</a></p><details><summary>运行环境、命令与证据边界</summary><pre>'
        + escape(json.dumps(manifest, ensure_ascii=False, indent=2))
        + "</pre></details></section>"
    )
    for index, row in enumerate(rows):
        parts.append(
            f'<article class="report-item" id="detail-{index}"><details><summary>'
            f"{index + 1} · {escape(row['case_name'])} / {escape(row['state_bytes'])} B / "
            f'{escape(row["distribution"])} / {escape(row["method"])}</summary><div class="detail-body">'
        )
        parts.append(
            "<table><thead><tr><th>阶段</th><th>墙钟 ns/行</th><th>CPU ns/行</th>"
            "<th>新分组数中位数</th><th>扩容次数中位数</th></tr></thead><tbody>"
        )
        for phase in range(1, 5):
            parts.append(
                f"<tr><td>{phase}</td><td>{median(row, f'phase{phase}_ns_per_op'):.3f}</td>"
                f"<td>{median(row, f'phase{phase}_cpu_ns_per_op'):.3f}</td>"
                f"<td>{median(row, f'phase{phase}_new_groups'):.0f}</td>"
                f"<td>{median(row, f'phase{phase}_rehashes'):.0f}</td></tr>"
            )
        parts.append(
            "</tbody></table><p>原始样本保留逐种子状态摘要、NULL 行数和所有分段计时。</p><pre>"
            + escape(json.dumps(row["samples"], ensure_ascii=False, indent=2))
            + "</pre></div></details></article>"
        )
    css, js = (LAB / "assets/report.css").read_text(), (LAB / "assets/report.js").read_text()
    title = "聚合 Hashmap：大状态、分离存储与延迟初始化"
    subtitle = escape(
        f"{manifest.get('started_at', '')} · states · "
        f"CPU {manifest.get('cpu', {}).get('selected', '未绑定')} · {manifest.get('status', '')}"
    )
    return (
        f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta name="referrer" content="no-referrer"><title>{title}</title><style>{css}</style></head>'
        f'<body><header><div class="eyebrow">LOCAL EXPERIMENT · 实测与证据</div><h1>{title}</h1>'
        f'<p class="muted">{subtitle}</p></header><main>{"".join(parts)}</main><script>{js}</script></body></html>'
    )
