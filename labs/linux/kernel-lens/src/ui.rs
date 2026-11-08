use crate::bench::{Kind, Session};
use crate::model::{Snapshot, State, Topic};
use ratatui::layout::{Constraint, Layout};
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Borders, Cell, Paragraph, Row, Table, TableState, Tabs, Wrap};
use ratatui::Frame;

#[derive(Default)]
pub struct View {
    pub tab: usize,
    pub selected: usize,
    pub filter: String,
    pub searching: bool,
    pub paused: bool,
    pub help: bool,
    pub detail: bool,
    pub summary_table: bool,
    pub detail_scroll: u16,
}

impl View {
    pub fn switch(&mut self, tab: usize) {
        self.tab = tab % Topic::ALL.len();
        self.selected = 0;
        self.filter.clear();
        self.detail = false;
        self.detail_scroll = 0;
    }

    pub fn row_count(&self, snapshot: &Snapshot) -> usize {
        self.rows(snapshot).len()
    }

    fn rows<'a>(&self, snapshot: &'a Snapshot) -> Vec<&'a crate::model::Metric> {
        let filter = self.filter.to_lowercase();
        snapshot
            .metrics
            .iter()
            .filter(|metric| {
                metric.topic == Topic::ALL[self.tab]
                    && (metric.name.to_lowercase().contains(&filter)
                        || metric.value.to_lowercase().contains(&filter))
            })
            .collect()
    }
}

pub fn draw(frame: &mut Frame, snapshot: &Snapshot, view: &View, age_secs: f64, session: &Session) {
    let area = frame.area();
    if area.width < 45 || area.height < 14 {
        frame.render_widget(
            Paragraph::new("kernel-lens\n请扩大终端到至少 45×14。\nq 退出 / Tab 切页")
                .wrap(Wrap { trim: false }),
            area,
        );
        return;
    }
    let layout = Layout::vertical([
        Constraint::Length(2),
        Constraint::Length(2),
        Constraint::Min(3),
        Constraint::Length(8),
        Constraint::Length(2),
    ])
    .split(area);
    let status = if view.paused { "PAUSED" } else { "LIVE" };
    let header = format!("kernel-lens  {status}  sample #{}  collection {}ms  age {:.1}s\nLinux 配置与观测 · scope 标明范围 · Benchmark 需选择后运行", snapshot.sequence, snapshot.collection_ms, age_secs);
    frame.render_widget(
        Paragraph::new(header).style(Style::default().fg(Color::Cyan)),
        layout[0],
    );
    frame.render_widget(
        Tabs::new(
            Topic::ALL
                .iter()
                .enumerate()
                .map(|(i, topic)| format!("{} {}", i + 1, topic.title())),
        )
        .select(view.tab)
        .highlight_style(
            Style::default()
                .fg(Color::Yellow)
                .add_modifier(Modifier::BOLD),
        ),
        layout[1],
    );
    if Topic::ALL[view.tab] == Topic::Benchmark {
        draw_bench(frame, layout[2].union(layout[3]), layout[4], session);
        return;
    }
    if Topic::ALL[view.tab] == Topic::Summary
        && !view.summary_table
        && !view.detail
        && view.filter.is_empty()
    {
        draw_summary(frame, layout[2].union(layout[3]), layout[4], snapshot);
        return;
    }
    let rows = view.rows(snapshot);
    let selected = view.selected.min(rows.len().saturating_sub(1));
    if view.detail {
        let topic = Topic::ALL[view.tab];
        let mut lines = vec![Line::from(topic.lesson()), Line::from("")];
        if let Some(metric) = rows.get(selected) {
            lines.extend([
                Line::from(format!("指标: {}", metric.name)),
                Line::from(format!("值: {} {}", metric.value, metric.unit)),
                Line::from(format!("状态: {:?}", metric.state)),
                Line::from(format!("scope: {}", metric.scope)),
                Line::from(format!("source: {}", metric.source)),
                Line::from(""),
                Line::from(metric.explanation.clone()),
            ]);
        }
        lines.push(Line::from(""));
        lines.push(Line::from(format!(
            "下一步（另开终端）: {}",
            topic.commands()
        )));
        let detail_area = ratatui::layout::Rect {
            x: layout[2].x,
            y: layout[2].y,
            width: layout[2].width,
            height: layout[2].height + layout[3].height,
        };
        frame.render_widget(
            Paragraph::new(lines)
                .wrap(Wrap { trim: false })
                .scroll((view.detail_scroll, 0))
                .block(Block::default().title(" 指标详情 ").borders(Borders::ALL)),
            detail_area,
        );
        frame.render_widget(
            Paragraph::new("↑↓/PgUp/PgDn 滚动  Enter/Esc 返回  q 退出"),
            layout[4],
        );
        return;
    }
    let table_rows = rows.iter().map(|metric| {
        let color = match metric.state {
            State::Ready => Color::Green,
            State::Warming => Color::Yellow,
            State::Unavailable => Color::DarkGray,
        };
        Row::new(vec![
            Cell::from(metric.name.clone()),
            Cell::from(format!("{} {}", metric.value, metric.unit))
                .style(Style::default().fg(color)),
            Cell::from(metric.scope.clone()),
        ])
    });
    let title = if view.filter.is_empty() {
        format!(
            " {} · {} observations ",
            Topic::ALL[view.tab].title(),
            rows.len()
        )
    } else {
        format!(" filter: {} · {} observations ", view.filter, rows.len())
    };
    let table = Table::new(
        table_rows,
        [
            Constraint::Percentage(27),
            Constraint::Percentage(45),
            Constraint::Percentage(28),
        ],
    )
    .header(
        Row::new(["指标", "观测值 / 单位", "scope / 统计范围"])
            .style(Style::default().fg(Color::Cyan)),
    )
    .block(Block::default().title(title).borders(Borders::ALL))
    .row_highlight_style(Style::default().bg(Color::DarkGray))
    .highlight_symbol("› ");
    let mut state = TableState::default().with_selected((!rows.is_empty()).then_some(selected));
    frame.render_stateful_widget(table, layout[2], &mut state);
    let topic = Topic::ALL[view.tab];
    let mut detail = vec![Line::from(Span::styled(
        topic.lesson(),
        Style::default().fg(Color::Yellow),
    ))];
    if let Some(metric) = rows.get(selected) {
        detail.push(Line::from(format!("source: {}", metric.source)));
        detail.push(Line::from(format!(
            "{}: {}",
            metric.name, metric.explanation
        )));
    }
    detail.push(Line::from(format!(
        "下一步（另开终端）: {}",
        topic.commands()
    )));
    if view.help {
        detail.push(Line::from("↑↓/jk 选指标；PgUp/PgDn 翻行；1–9/Tab 切页；/ 搜索；Esc 清除；空格暂停；q/Ctrl-C 退出。"));
    }
    frame.render_widget(
        Paragraph::new(detail).wrap(Wrap { trim: false }).block(
            Block::default()
                .title(" 来源 · 含义 · 观察方法 ")
                .borders(Borders::ALL),
        ),
        layout[3],
    );
    let footer = if view.searching {
        format!("搜索: {}▏  Enter 确认 / Esc 清除", view.filter)
    } else {
        "Tab/1–9 切页  ↑↓/jk 选择  / 搜索  Enter 详情  Space 暂停  ? 帮助  q 退出".into()
    };
    frame.render_widget(Paragraph::new(footer).wrap(Wrap { trim: false }), layout[4]);
}

fn draw_bench(
    frame: &mut Frame,
    area: ratatui::layout::Rect,
    footer: ratatui::layout::Rect,
    session: &Session,
) {
    if session.detail {
        let kind = Kind::ALL[session.cursor];
        let mut lines = vec![
            Line::from(kind.label()),
            Line::from(kind.explanation()),
            Line::from(""),
        ];
        if let Some((_, result)) = session
            .results
            .iter()
            .find(|(candidate, _)| *candidate == kind)
        {
            match result {
                Ok(report) => {
                    lines.push(Line::from(format!(
                        "{} / {} rounds / {}ms / {}MiB / workload v{}",
                        report.build_mode,
                        report.config.rounds,
                        report.config.duration_ms,
                        report.config.size_mib,
                        report.workload_version
                    )));
                    for m in &report.measurements {
                        lines.push(Line::from(format!(
                            "{}: median {:.3} {} / min {:.3} / max {:.3} / rounds {:?}",
                            m.name, m.median, m.unit, m.min, m.max, m.values
                        )));
                    }
                    lines.push(Line::from("环境配置:"));
                    for (key, value) in &report.environment {
                        lines.push(Line::from(format!("{key}: {value}")));
                    }
                    for (title, observations) in [
                        ("测试前", &report.observations_before),
                        ("测试后", &report.observations_after),
                    ] {
                        lines.push(Line::from(title));
                        for m in observations {
                            lines.push(Line::from(format!(
                                "{}: {} {} [{}]",
                                m.name, m.value, m.unit, m.scope
                            )));
                        }
                    }
                    for note in &report.notes {
                        lines.push(Line::from(note.as_str()));
                    }
                }
                Err(error) => lines.push(Line::from(
                    error
                        .chars()
                        .map(|c| if c.is_control() { ' ' } else { c })
                        .collect::<String>(),
                )),
            }
        } else {
            lines.push(Line::from(
                "此项目尚无结果。Enter 返回后 Space 勾选、r 运行。",
            ));
        }
        frame.render_widget(
            Paragraph::new(lines)
                .wrap(Wrap { trim: false })
                .scroll((session.result_scroll, 0))
                .block(
                    Block::default()
                        .title(" 基准条件与结果 ")
                        .borders(Borders::ALL),
                ),
            area,
        );
        frame.render_widget(
            Paragraph::new("PgUp/PgDn 滚动  ↑↓ 切换项目  Enter/Esc 返回  c 取消  q 退出"),
            footer,
        );
        return;
    }
    let parts = Layout::vertical([
        Constraint::Length(3),
        Constraint::Length(8),
        Constraint::Length(4),
        Constraint::Min(3),
    ])
    .split(area);
    let config = &session.config;
    frame.render_widget(Paragraph::new(format!("{} ms/轮 × {} 轮 · 内存/文件 {} MiB · 结果保留每轮及 median/min/max\n编译模式: {} · 文件目录: {}", config.duration_ms, config.rounds, config.size_mib,
        if cfg!(debug_assertions) { "debug；性能比较请用 release" } else { "release" }, config.directory.as_ref().map(|p|p.display().to_string()).unwrap_or_else(||"未设置（文件测试不可运行）".into()))).wrap(Wrap {trim:false}), parts[0]);
    let rows = Kind::ALL.iter().enumerate().map(|(index, kind)| {
        let checked = if session.selected[index] {
            "[x]"
        } else {
            "[ ]"
        };
        let status = if session.active == Some(*kind) {
            "运行中"
        } else if *kind == Kind::FileIo && config.directory.is_none() {
            "需 --bench-dir"
        } else {
            "就绪"
        };
        Row::new(vec![
            checked.to_owned(),
            kind.label().to_owned(),
            status.to_owned(),
        ])
    });
    let table = Table::new(
        rows,
        [
            Constraint::Length(5),
            Constraint::Min(20),
            Constraint::Length(18),
        ],
    )
    .block(
        Block::default()
            .title(" 选择测试（不会自动运行） ")
            .borders(Borders::ALL),
    )
    .row_highlight_style(Style::default().bg(Color::DarkGray));
    frame.render_stateful_widget(
        table,
        parts[1],
        &mut TableState::default().with_selected(Some(session.cursor)),
    );
    frame.render_widget(
        Paragraph::new(format!(
            "{}\n{}",
            session.message,
            Kind::ALL[session.cursor].explanation()
        ))
        .wrap(Wrap { trim: false }),
        parts[2],
    );
    let mut lines = Vec::new();
    for (kind, result) in &session.results {
        match result {
            Ok(report) => {
                for measurement in &report.measurements {
                    lines.push(Line::from(format!(
                        "{}: {:.3} {}  [min {:.3}, max {:.3}]",
                        kind.id(),
                        measurement.median,
                        measurement.unit,
                        measurement.min,
                        measurement.max
                    )));
                    lines.push(Line::from(format!(
                        "  {} · 每轮 {:?}",
                        measurement.name,
                        measurement
                            .values
                            .iter()
                            .map(|n| format!("{n:.3}"))
                            .collect::<Vec<_>>()
                    )));
                }
            }
            Err(error) => lines.push(Line::from(format!(
                "{}: {}",
                kind.id(),
                error
                    .chars()
                    .map(|c| if c.is_control() { ' ' } else { c })
                    .collect::<String>()
            ))),
        }
    }
    if lines.is_empty() {
        lines.push(Line::from(
            "尚无结果。先核对机器总览中的 CPU 许可、配额与内存上限，再选择测试。",
        ));
    }
    frame.render_widget(
        Paragraph::new(lines)
            .wrap(Wrap { trim: false })
            .scroll((session.result_scroll, 0))
            .block(
                Block::default()
                    .title(" 本次测量（不是整机评分） ")
                    .borders(Borders::ALL),
            ),
        parts[3],
    );
    frame.render_widget(
        Paragraph::new(
            "↑↓ 选择  Space 勾选  r 运行选中项  c 取消  Enter 详情  PgDn 结果  1 总览  q 退出",
        ),
        footer,
    );
}

fn summary_value(metric: &crate::model::Metric) -> String {
    if metric.name.starts_with("容器 · 内存") {
        if metric.value == "max" {
            return "本层不设上限（祖先限制未知）".into();
        }
        if let Ok(bytes) = metric.value.parse::<u64>() {
            return format!("{:.2} GiB ({} bytes)", bytes as f64 / 1073741824.0, bytes);
        }
    }
    if metric.name == "容器 · CPU 配额" {
        let fields = metric.value.split_whitespace().collect::<Vec<_>>();
        if fields.len() == 2 {
            if fields[0] == "max" {
                return "本层不设 CPU 时间配额".into();
            }
            if let (Ok(quota), Ok(period)) = (fields[0].parse::<f64>(), fields[1].parse::<f64>()) {
                if period > 0.0 {
                    return format!("{:.2} 核时间配额 [{} µs]", quota / period, metric.value);
                }
            }
        }
    }
    metric.value.clone()
}

fn draw_summary(
    frame: &mut Frame,
    area: ratatui::layout::Rect,
    footer: ratatui::layout::Rect,
    snapshot: &Snapshot,
) {
    let rows = Layout::vertical([
        Constraint::Ratio(1, 3),
        Constraint::Ratio(1, 3),
        Constraint::Ratio(1, 3),
    ])
    .split(area);
    let groups = [
        (" CPU / NUMA 可见配置 ", vec!["CPU", "NUMA"]),
        (" 内存 / 当前容器限制 ", vec!["内存", "容器"]),
        (" 网络接口（当前 namespace） ", vec!["网络"]),
        (" 存储可见配置 ", vec!["存储"]),
        (" 系统环境 ", vec!["系统"]),
        (" 当前负载（范围见明细） ", vec!["当前"]),
    ];
    for (index, (title, prefixes)) in groups.iter().enumerate() {
        let columns = Layout::horizontal([Constraint::Ratio(1, 2), Constraint::Ratio(1, 2)])
            .split(rows[index / 2]);
        let panel = columns[index % 2];
        let mut lines: Vec<Line> = snapshot
            .metrics
            .iter()
            .filter(|m| {
                m.topic == Topic::Summary
                    && prefixes.iter().any(|prefix| m.name.starts_with(prefix))
            })
            .map(|m| Line::from(format!("{}: {} {}", m.name, summary_value(m), m.unit)))
            .collect();
        if index == 0 {
            // Keep the permission/NUMA summary visible before the cache detail rows.
            lines = snapshot
                .metrics
                .iter()
                .filter(|m| {
                    m.topic == Topic::Summary
                        && prefixes.iter().any(|prefix| m.name.starts_with(prefix))
                        && !m.name.contains("cache")
                })
                .map(|m| Line::from(format!("{}: {} {}", m.name, summary_value(m), m.unit)))
                .collect();
            let cache = snapshot
                .metrics
                .iter()
                .filter(|m| m.topic == Topic::Summary && m.name.contains("cache"))
                .map(|m| m.value.split(" / ").next().unwrap_or(&m.value))
                .collect::<Vec<_>>();
            if !cache.is_empty() {
                lines.push(Line::from(format!("cpu0 cache: {}", cache.join("; "))));
            }
        }
        if index == 5 {
            for metric in snapshot.metrics.iter().filter(|m| {
                m.name == "procs_running"
                    || m.name == "procs_blocked"
                    || m.name == "load 1/5/15m, runnable/total, last PID"
            }) {
                lines.push(Line::from(format!("{}: {}", metric.name, metric.value)));
            }
            lines.push(Line::from("9 → 选择 Benchmark；默认不运行测试"));
        }
        if lines.is_empty() {
            lines.push(Line::from("N/A · 详细原因见 Enter 明细"));
        }
        let capacity = panel.height.saturating_sub(2) as usize;
        if capacity > 0 && lines.len() > capacity {
            lines.truncate(capacity);
            lines[capacity - 1] = Line::from("… Enter 展开全部指标与来源");
        }
        frame.render_widget(
            Paragraph::new(lines).block(
                Block::default()
                    .title(*title)
                    .borders(Borders::ALL)
                    .border_style(Style::default().fg(Color::Cyan)),
            ),
            panel,
        );
    }
    frame.render_widget(
        Paragraph::new("Enter 全部配置/来源  9 选择性能测试  2–8 专项观测  Space 暂停  q 退出"),
        footer,
    );
}

#[cfg(test)]
mod tests {
    use super::*;
    use ratatui::{backend::TestBackend, Terminal};
    #[test]
    fn renders_all_topics_in_large_and_tiny_terminals() {
        let snapshot =
            crate::collectors::Kernel::new(crate::collectors::LinuxFs::new("/does-not-exist"))
                .sample();
        let session = Session::new(crate::bench::Config::default());
        for (width, height) in [(120, 35), (45, 14), (20, 5), (1, 1)] {
            let mut terminal = Terminal::new(TestBackend::new(width, height)).unwrap();
            for tab in 0..Topic::ALL.len() {
                let view = View {
                    tab,
                    selected: usize::MAX,
                    help: true,
                    ..View::default()
                };
                terminal
                    .draw(|frame| draw(frame, &snapshot, &view, 0.0, &session))
                    .unwrap();
                let expanded = View {
                    detail: true,
                    ..view
                };
                terminal
                    .draw(|frame| draw(frame, &snapshot, &expanded, 0.0, &session))
                    .unwrap();
            }
        }
    }
}
