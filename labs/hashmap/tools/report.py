"""Build a self-contained, offline HTML report from measured CSV samples (stdlib only)."""

import argparse
from collections import defaultdict
import csv
import html
import json
import math
from pathlib import Path
import statistics

LAB = Path(__file__).resolve().parents[1]
GROUP_FIELDS = (
    "mode",
    "case_name",
    "key_type",
    "n",
    "method",
    "hit",
    "distribution",
    "target_load",
    "ndv_config",
    "domain",
    "null_percent",
    "state_bytes",
)
BASE_FIELDS = tuple(field for field in GROUP_FIELDS if field != "method")


def escape(value):
    return html.escape(str(value), quote=True)


def summarize(samples):
    groups = defaultdict(list)
    for sample in samples:
        value = float(sample["ns_per_op"])
        if not math.isfinite(value) or value <= 0 or int(sample["operations"]) <= 0:
            raise ValueError("non-positive measured time/operations")
        groups[tuple(sample.get(field, "") for field in GROUP_FIELDS)].append(sample)
    result = []
    for key, rows in groups.items():
        row = dict(zip(GROUP_FIELDS, key))
        values = [float(sample["ns_per_op"]) for sample in rows]
        row.update(
            median=statistics.median(values),
            minimum=min(values),
            maximum=max(values),
            samples=rows,
            sample_count=len(rows),
            seeds=len({r["seed"] for r in rows}),
            map_bytes=int(rows[0]["map_bytes"]),
            key_bytes=int(rows[0]["key_payload_bytes"]),
            capacity=int(rows[0]["capacity"]),
            actual_load=float(rows[0]["actual_load"]),
            algorithm=rows[0]["algorithm"],
        )
        row["spread_pct"] = (row["maximum"] - row["minimum"]) / row["median"] * 100
        probes = [float(r["mean_probes"]) for r in rows if r["mean_probes"]]
        row["probes"] = statistics.mean(probes) if probes else None
        row["max_probes"] = max(
            (int(r["max_probes"]) for r in rows if r["max_probes"]), default=None
        )
        result.append(row)
    baselines = {
        tuple(row[field] for field in BASE_FIELDS): row["median"]
        for row in result
        if row["method"] == ("bucket" if row["mode"].startswith("join-") else "std")
    }
    for row in result:
        baseline = baselines.get(tuple(row[field] for field in BASE_FIELDS))
        row["baseline_method"] = "bucket" if row["mode"].startswith("join-") else "std"
        row["baseline"] = baseline
        row["delta_ns"] = row["median"] - baseline if baseline is not None else None
        row["delta_pct"] = (row["median"] / baseline - 1) * 100 if baseline else None
        row["speedup"] = baseline / row["median"] if baseline else None
    return sorted(
        result,
        key=lambda row: (
            row["mode"],
            row["case_name"],
            int(row["hit"]),
            row["distribution"],
            float(row["target_load"]),
            row["method"],
        ),
    )


def render(manifest, samples):
    rows = summarize(samples)
    if manifest.get("family") == "states":
        from state_report import render as render_states

        return render_states(manifest, rows), rows
    operators = manifest.get("family") == "operators"
    css = (LAB / "assets/report.css").read_text()
    js = (LAB / "assets/report.js").read_text()
    parts = [
        '<nav><a href="#overview">结论与边界</a><a href="#measurements">性能对照</a>'
        '<a href="#evidence">环境与证据</a></nav>',
        '<section id="overview"><h2>实测总览</h2>',
        '<div class="cards">',
    ]
    for number, text in [
        (len(rows), "组汇总对照"),
        (len(samples), "条真实计时样本"),
        (len(manifest.get("jobs", [])), "个独立工作进程"),
        (manifest.get("failed_jobs", 0), "个执行失败"),
    ]:
        parts.append(
            f'<div class="card"><strong>{escape(number)}</strong><span>{escape(text)}</span></div>'
        )
    if operators:
        parts.append(
            "</div><p>StarRocks 机制启发的独立实验；没有链接或运行 StarRocks。"
            "聚合测完整 COUNT/SUM 状态更新周期（包含建表、扩容和销毁）；Join build 测建表与销毁；"
            "Join probe 测匹配计数与行号求和，不包含输出行物化；Semi Join 仅判断存在性。</p>"
        )
        parts.append(
            "<p>std 是聚合/存在性基线；bucket 是重复键 Join 基线。所有值与 NULL 语义逐项核对。"
            "direct 使用运行期已知的有限整数范围，不要求编译期知道实际键集合。"
            "flat-fp 与 flat-bytes 对照 2×32 位复合键的整数打包与 8 字节键布局；键编码在计时外完成。</p>"
        )
        parts.append(
            '<div class="notice">phases 依次输入窄键域、扩大键域、前端热点、尾端热点，'
            "聚合过程中会出现新分组；表中是完整流的均摊时间，尚无逐阶段延迟。"
            "空值单列：聚合 NULL 为一个分组；普通等值 Join 中 NULL 不匹配 NULL。"
            "未测试 null-safe Join 或 NOT IN 的三值逻辑。</div>"
        )
        noisy = sum(row["spread_pct"] > 20 for row in rows)
        parts.append(
            f"<p>当前 {noisy}/{len(rows)} 组的样本最大最小范围超过中位数的 20%。"
            "同时展示墙钟与进程 CPU 耗时，以便观察等待影响；这不能独立证明干扰根因。"
            "平均/最大访问步数包括索引槽与行链访问，键比较次数独立计数，均在计时外诊断。</p></section>"
        )
        parts.append(
            "<section><h2>代表场景：基线与专用结构</h2>"
            '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:14px">'
        )
        for case in sorted({row["case_name"] for row in rows}):
            selected = [
                row
                for row in rows
                if row["case_name"] == case
                and (
                    (row["mode"] == "aggregate" and row["distribution"] == "phases")
                    or (row["mode"] in ("join-probe", "semi-probe") and row["hit"] == "50")
                )
            ]
            if not selected:
                continue
            distribution = selected[0]["distribution"]
            selected = [row for row in selected if row["distribution"] == distribution]
            maximum = max(row["median"] for row in selected)
            parts.append(
                f'<div class="card"><h3>{escape(case)} / {escape(distribution)}</h3>'
                f'<svg viewBox="0 0 460 {len(selected) * 34 + 20}" role="img" '
                f'aria-label="{escape(case)} 耗时 ns/输入行" style="width:100%;height:auto">'
            )
            for index, row in enumerate(selected):
                y = 10 + index * 34
                width = row["median"] / maximum * 250
                parts.append(
                    f'<text x="0" y="{y + 16}" font-size="12">{escape(row["method"])}</text>'
                    f'<rect x="90" y="{y}" width="{width:.2f}" height="23" fill="#11666b"/>'
                    f'<text x="{98 + width:.2f}" y="{y + 16}" font-size="12">{row["median"]:.2f}</text>'
                )
            parts.append("</svg></div>")
        parts.append("</div></section>")
    else:
        parts.append(
            "</div><p>表中耗时包含查询循环和结果累加。查找是预热后的独立请求吞吐，"
            "ns/op 为批量平均耗时；不代表依赖链延迟或单次请求 P99。默认显示跨种子、跨重复的中位数。</p>"
        )
        observations = []
        for method in ("linear", "perfect", "wide", "sorted"):
            candidate = next(
                (
                    row
                    for row in rows
                    if row["case_name"] == "short64"
                    and row["hit"] == "100"
                    and row["distribution"] == "uniform"
                    and row["mode"] == "lookup"
                    and row["target_load"] == "0.75"
                    and row["method"] == method
                ),
                None,
            )
            if candidate and candidate["speedup"]:
                observations.append(
                    f"<li>short64、均匀全命中：{escape(method)} 中位数 "
                    f"{candidate['median']:.2f} ns/op，std 基线 {candidate['baseline']:.2f} ns/op，"
                    f"基线耗时 / 当前耗时 = {candidate['speedup']:.2f}×。</li>"
                )
        if observations:
            parts.append("<ul>" + "".join(observations) + "</ul>")
        parts.append(
            '<div class="notice">单机共享环境实测；波动不自动归因于算法。最大最小值来自批量样本，'
            "不是操作尾延迟。perfect/wide 键集合在编译期固定，动态增删不适用。"
            "未采集硬件计数器，探测次数来自计时结束后的单独诊断。</div>"
        )
        parts.append(
            "<p>std 与 linear 使用相同 FNV-1a + 混合哈希；perfect 使用自身算法，属于完整实现对照。"
            "字符串值统一为 uint32_t，键存储由实验台持有，查询字符与建表键分开存储。"
            "build-reserved / build-growing 衡量完整的构建并销毁周期（ns/插入键）；"
            "churn 是成对替换再恢复，每组四次增删操作。</p></section>"
        )
        parts.append(
            "<section><h2>固定键查找：均匀全命中</h2><p>每张图使用自己的横轴范围；单位 ns/op，越短越快。"
            "仅展示目标负载率 0.75 的样本，完整命中率与热点对照见下表。</p>"
            '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:14px">'
        )
        for case in sorted(
            {
                row["case_name"]
                for row in rows
                if row["mode"] == "lookup" and row["method"] == "perfect"
            }
        ):
            selected = [
                row
                for row in rows
                if row["case_name"] == case
                and row["mode"] == "lookup"
                and row["hit"] == "100"
                and row["distribution"] == "uniform"
                and row["target_load"] == "0.75"
            ]
            if not selected:
                continue
            maximum = max(row["median"] for row in selected)
            parts.append(
                f'<div class="card"><h3>{escape(case)}</h3>'
                f'<svg viewBox="0 0 420 {len(selected) * 34 + 20}" role="img" '
                f'aria-label="{escape(case)} 全命中耗时柱状图" style="width:100%;height:auto">'
            )
            for index, row in enumerate(selected):
                y = 10 + index * 34
                width = row["median"] / maximum * 230
                fill = "#112f41" if row["method"] == "std" else "#11666b"
                parts.append(
                    f'<text x="0" y="{y + 16}" font-size="13">{escape(row["method"])}</text>'
                    f'<rect x="70" y="{y}" width="{width:.2f}" height="23" fill="{fill}" rx="2"/>'
                    f'<text x="{78 + width:.2f}" y="{y + 16}" font-size="12">{row["median"]:.2f}</text>'
                )
            parts.append("</svg></div>")
        parts.append("</div></section>")
    parts.append(
        '<section id="measurements" data-report-explorer><h2>性能与存储对照'
        "<small>负差表示比相同场景基线耗时低；筛选只改变可见行。点击明细查看种子、原始计时和校验和。</small></h2>"
        '<div class="controls"><label>搜索<input data-report-search placeholder="case / 算法 / 方法"></label>'
    )
    for field, label in [
        ("mode", "阶段"),
        ("method", "实现"),
        ("distribution", "分布"),
        ("hit", "命中率"),
    ]:
        values = sorted({row[field] for row in rows})
        parts.append(
            f'<label>{label}<select data-report-filter="{field}"><option value="all">全部</option>'
        )
        parts.extend(
            f'<option value="{escape(value)}">{escape(value)}</option>' for value in values
        )
        parts.append("</select></label>")
    parts.append(
        '<label>排序<select data-report-sort><option value="">默认</option>'
        '<option value="ns:asc">耗时升序</option><option value="delta:desc">退化优先</option>'
        '<option value="delta:asc">下降优先</option><option value="spread:desc">波动优先</option>'
        "</select></label><button data-report-reset>重置</button><span data-report-count></span></div>"
        '<div class="table-scroll index"><table data-report-table><thead><tr>'
    )
    columns = [
        "明细",
        "阶段 / 数据",
        "N / 命中 / 分布",
        "实现 / 算法",
        "目标 / 实际占用率",
        "基线 ns/op",
        "当前 ns/op",
        "差值 ns / %",
        "样本 min～max",
        "波动范围 %",
        "表存储 B",
        "键载荷 B",
        "探测均值 / 最大",
        "样本 / 种子",
    ]
    if operators:
        columns.extend(
            ["非空分组 / NULL 行", "实际 probe 命中率", "CPU ns/输入行", "平均键比较次数"]
        )
    parts.extend(f"<th>{title}</th>" for title in columns)
    parts.append("</tr></thead><tbody>")
    for index, row in enumerate(rows):
        attrs = " ".join(
            f'data-{field}="{escape(row[field])}"'
            for field in ("mode", "method", "distribution", "hit")
        )
        delta_attr = "" if row["delta_pct"] is None else str(row["delta_pct"])
        parts.append(
            f'<tr {attrs} data-ns="{row["median"]}" data-delta="{delta_attr}" '
            f'data-spread="{row["spread_pct"]}">'
        )
        baseline = "未测" if row["baseline"] is None else f"{row['baseline']:.3f}"
        delta = (
            "不可计算"
            if row["delta_ns"] is None
            else f"{row['delta_ns']:+.3f} / {row['delta_pct']:+.1f}%"
        )
        direction = (
            ""
            if row["delta_ns"] is None or row["delta_ns"] == 0
            else ("up" if row["delta_ns"] > 0 else "down")
        )
        probes = "未采集" if row["probes"] is None else f"{row['probes']:.2f} / {row['max_probes']}"
        cells = [
            f'<a href="#detail-{index}">{index + 1}</a>',
            escape(row["mode"]) + "<br>" + escape(row["case_name"]),
            f"{escape(row['n'])} / {escape(row['hit'])}% / {escape(row['distribution'])}",
            escape(row["method"]) + "<small>" + escape(row["algorithm"]) + "</small>",
            f"{float(row['target_load']):.2f} / {row['actual_load']:.3f}",
            baseline + "<small>" + escape(row["baseline_method"]) + "</small>",
            f"<strong>{row['median']:.3f}</strong>",
            f'<span class="{direction}">{delta}</span>',
            f"{row['minimum']:.3f}～{row['maximum']:.3f}",
            f"{row['spread_pct']:.1f}",
            str(row["map_bytes"]),
            str(row["key_bytes"]),
            probes,
            f"{row['sample_count']} / {row['seeds']}",
        ]
        if operators:
            first = row["samples"][0]
            cpu = statistics.median(float(sample["cpu_ns_per_op"]) for sample in row["samples"])
            comparisons = [
                float(sample["mean_comparisons"])
                for sample in row["samples"]
                if sample["mean_comparisons"]
            ]
            cells.extend(
                [
                    escape(first["ndv"]) + " / " + escape(first["null_rows"]),
                    f"{float(first['actual_hit_ratio']) * 100:.1f}%"
                    if row["mode"] in ("join-probe", "semi-probe")
                    else "不适用",
                    f"{cpu:.3f}",
                    f"{statistics.mean(comparisons):.3f}" if comparisons else "未采集",
                ]
            )
        parts.extend(f"<td>{cell}</td>" for cell in cells)
        parts.append("</tr>")
    if operators:
        parts.append(
            "</tbody></table></div><p>表存储为数组容量、对象与存活分配请求字节；不含分配器元数据或输入行。"
            "direct aggregate 内联 16 字节 COUNT/SUM 状态，bitmap 每个域值一位，Join 链为数组行号。"
            "N 为聚合输入行数或 Join 构建行数，probe 固定 16384 行。实际占用率为非空不同键数 / 容量，"
            "不是 Join 重复行碰撞密度。phases 的不同种子可能产生略有差异的实际分组数；逐样本值保留在明细中。"
            "聚合的命中率列不适用；键载荷按构建输入每行逻辑 8 字节列示，编码/复制成本在计时外。"
            "不代表完整 SQL 算子或 StarRocks 的性能。</p></section>"
        )
    else:
        parts.append(
            "</tbody></table></div><p>表存储：std 为 allocator 请求的存活字节 + 对象大小；linear/sorted 为数组容量字节 + 对象大小；"
            "perfect 为 sizeof(编译期表)。不含分配器元数据、查询轨迹、共享输入字面量或进程其它部分。"
            "这些是存储口径，不是独立物理内存占用。键载荷单列，不能用进程 RSS 相减代替。"
            "容量和占用率含义随实现不同；sorted 的占用率不是哈希负载率。</p></section>"
        )
    parts.append(
        '<section id="evidence"><h2>环境、构建与原始证据</h2>'
        '<p><a href="samples.csv">原始 CSV</a> · <a href="manifest.json">运行清单</a> · '
        '<a href="summary.json">汇总 JSON</a> · <a href="tests.log">测试日志</a> · '
        '<a href="build.log">构建日志</a> · <a href="events.jsonl">进度事件</a></p>'
    )
    build = manifest.get("build", {})
    parts.append(
        f"<p>构建墙钟：{escape(build.get('wall_seconds', '未测'))} 秒；"
        f"构建命令及其子进程峰值 RSS：{escape(build.get('peak_rss_kib', '未测'))} KiB。"
        f"构建类型：{escape(build.get('kind', '未测'))}。这是整套实验台的构建，包含 perfect 常量求值，"
        "不等同于 perfect 算法独立生成时间。</p>"
    )
    parts.append(
        "<details><summary>完整环境与运行清单</summary><pre>"
        + escape(json.dumps(manifest, ensure_ascii=False, indent=2))
        + "</pre></details></section>"
    )
    for index, row in enumerate(rows):
        parts.append(
            f'<article class="report-item" id="detail-{index}"><details><summary>'
            f"{index + 1} · {escape(row['case_name'])} / {escape(row['mode'])} / {escape(row['method'])} / "
            f'{row["hit"]}% / {escape(row["distribution"])}</summary><div class="detail-body">'
            "<p>ns/op = elapsed_ns / operations；每个工作进程在计时前逐键、逐查询核验，"
            "查找计时结果再次检查校验和；错误会使进程非零退出。</p><pre>"
            + escape(json.dumps(row["samples"], ensure_ascii=False, indent=2))
            + "</pre></div></details></article>"
        )
    body = "".join(parts)
    title = "分析型算子专用 Hashmap 实验" if operators else "Hashmap 本地性能实验"
    subtitle = escape(
        f"{manifest.get('started_at', '')} · {manifest.get('suite', '')} · "
        f"CPU {manifest.get('cpu', {}).get('selected', '未绑定')} · {manifest.get('status', '')}"
    )
    document = (
        f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta name="referrer" content="no-referrer"><title>{title}</title><style>{css}</style></head>'
        f'<body><header><div class="eyebrow">LOCAL EXPERIMENT · 实测与证据</div><h1>{title}</h1>'
        f'<p class="muted">{subtitle}</p></header><main>{body}</main><script>{js}</script></body></html>'
    )
    return document, rows


def generate(directory):
    manifest = json.loads((directory / "manifest.json").read_text())
    with (directory / "samples.csv").open(newline="") as handle:
        samples = list(csv.DictReader(handle))
    content, rows = render(manifest, samples)
    output = directory / "report.html"
    with output.open("x", encoding="utf-8") as handle:
        handle.write(content)
    (directory / "summary.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2))
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    print(generate(parser.parse_args().directory).resolve())
