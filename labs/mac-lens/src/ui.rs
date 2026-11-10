use crate::collect::Completed;
use crate::model::{Process, Snapshot};
use ratatui::{
    layout::{Constraint, Layout, Rect},
    style::{Color, Modifier, Style},
    text::{Line, Text},
    widgets::{Block, Borders, Paragraph, Row, Sparkline, Table, Wrap},
    Frame,
};
use std::collections::VecDeque;

const CYAN: Color = Color::Rgb(90, 210, 225);
const GREEN: Color = Color::Rgb(136, 211, 150);
const DIM: Color = Color::Rgb(140, 153, 175);

#[derive(Default)]
pub struct View {
    pub paused: bool,
    pub focus: bool,
    pub memory_sort: bool,
    pub details: bool,
    pub scroll: u16,
    cpu_history: VecDeque<u64>,
    gpu_history: VecDeque<u64>,
    sequence: u64,
}

impl View {
    pub fn observe(&mut self, s: &Snapshot) {
        if self.sequence == s.sequence {
            return;
        }
        self.sequence = s.sequence;
        self.cpu_history
            .push_back(s.cpu_percent.clamp(0.0, 100.0) as u64);
        if let Some(gpu) = s.gpu.active_percent {
            self.gpu_history.push_back(gpu.clamp(0.0, 100.0) as u64);
        } else {
            self.gpu_history.clear();
        }
        while self.cpu_history.len() > 120 {
            self.cpu_history.pop_front();
        }
        while self.gpu_history.len() > 120 {
            self.gpu_history.pop_front();
        }
    }
}

pub fn bytes(n: u64) -> String {
    let value = n as f64;
    if n >= 1024 * 1024 * 1024 {
        format!("{:.1} GiB", value / (1024.0 * 1024.0 * 1024.0))
    } else if n >= 1024 * 1024 {
        format!("{:.1} MiB", value / (1024.0 * 1024.0))
    } else {
        format!("{:.1} KiB", value / 1024.0)
    }
}

fn number(value: Option<f64>, suffix: &str) -> String {
    value
        .map(|v| format!("{v:.1}{suffix}"))
        .unwrap_or_else(|| "N/A".into())
}

fn rate(value: Option<f64>) -> String {
    value
        .map(|n| format!("{:.1}", n / 1024.0))
        .unwrap_or_else(|| "N/A".into())
}

fn block(title: &str) -> Block<'_> {
    Block::default()
        .title(title)
        .borders(Borders::ALL)
        .border_style(Style::default().fg(DIM))
}

fn card(frame: &mut Frame, area: Rect, title: &str, lines: Vec<String>, color: Color) {
    frame.render_widget(
        Paragraph::new(lines.into_iter().map(Line::from).collect::<Vec<_>>())
            .style(Style::default().fg(color))
            .block(block(title))
            .wrap(Wrap { trim: false }),
        area,
    );
}

pub fn draw(frame: &mut Frame, completed: Option<&Completed>, error: Option<&str>, view: &View) {
    let area = frame.area();
    frame.render_widget(
        Block::default().style(
            Style::default()
                .bg(Color::Rgb(14, 20, 30))
                .fg(Color::Rgb(220, 229, 240)),
        ),
        area,
    );
    let Some(completed) = completed else {
        frame.render_widget(
            Paragraph::new(format!(
                "MAC LENS / read-only\n\n{}\n\nq / Ctrl-C: quit",
                error
                    .unwrap_or("Starting native sampler; first sample may take several seconds...")
            ))
            .block(block(" Waiting for telemetry ")),
            area,
        );
        return;
    };
    let s = &completed.sample;
    let age = completed.at.elapsed().as_secs_f64();
    let state = if view.paused {
        "PAUSED"
    } else if error.is_some() || age > 5.0 {
        "STALE"
    } else {
        "LIVE"
    };
    if area.width < 90 || area.height < 30 {
        frame.render_widget(Paragraph::new(format!(
            "MAC LENS [{state}] age {age:.1}s\nCPU {:.1}% | GPU {}\nRAM {} / {} | pressure {}\nSwap {} | generation {}\n\nResize to >=90x30 for dashboard.\nq quit | Space pause | Tab details\n\n{}",
            s.cpu_percent, number(s.gpu.active_percent, "% active"), bytes(s.memory.used), bytes(s.memory.total),
            s.memory.pressure.as_deref().unwrap_or("N/A"), bytes(s.memory.swap_used), number(s.inference.generation_tps, " tok/s"),
            error.unwrap_or(&s.gpu.reason))).block(block(" Compact view ")).wrap(Wrap { trim: false }), area);
        return;
    }
    let layout = Layout::vertical([
        Constraint::Length(3),
        Constraint::Min(20),
        Constraint::Length(1),
    ])
    .split(area);
    let header = format!(
        " MAC LENS  /  {}  | {state}  age {age:.1}s  sample #{}  window {}ms{}",
        s.cpu_model,
        s.sequence,
        s.sampling_ms,
        error.map(|e| format!("  {e}")).unwrap_or_default()
    );
    frame.render_widget(
        Paragraph::new(header)
            .style(Style::default().fg(CYAN).add_modifier(Modifier::BOLD))
            .block(block(" macOS inference / system-wide telemetry ")),
        layout[0],
    );
    if view.details {
        details(frame, layout[1], s, view);
    } else {
        dashboard(frame, layout[1], s, view);
    }
    frame.render_widget(Paragraph::new(" q/Ctrl-C quit   Space pause   Tab/1/2 dashboard/details   f candidates   m CPU/RAM sort   j/k scroll details ")
        .style(Style::default().fg(DIM)), layout[2]);
}

fn dashboard(frame: &mut Frame, area: Rect, s: &Snapshot, view: &View) {
    let sections = Layout::vertical([
        Constraint::Length(7),
        Constraint::Length(4),
        Constraint::Min(7),
        Constraint::Length(6),
    ])
    .split(area);
    let cards = Layout::horizontal([Constraint::Percentage(25); 4]).split(sections[0]);
    card(
        frame,
        cards[0],
        " CPU / all logical cores ",
        vec![
            format!("{:.1}% busy  / {} cores", s.cpu_percent, s.cores.len()),
            format!("Load 1m {:.2}", s.load_one),
            format!(
                "Busiest core {:.1}%",
                s.cores.iter().copied().fold(0.0, f64::max)
            ),
            format!("CPU power {}", number(s.gpu.cpu_power_watts, " W")),
        ],
        GREEN,
    );
    card(
        frame,
        cards[1],
        " Apple GPU / system-wide ",
        vec![
            number(s.gpu.active_percent, "% active residency"),
            format!(
                "{} MHz",
                s.gpu
                    .frequency_mhz
                    .map(|v| v.to_string())
                    .unwrap_or_else(|| "N/A".into())
            ),
            format!(
                "{} | {}",
                number(s.gpu.power_watts, " W"),
                number(s.gpu.temperature_c, " C")
            ),
            "Unified RAM; not dedicated VRAM".into(),
        ],
        CYAN,
    );
    card(
        frame,
        cards[2],
        " Unified memory / pressure ",
        vec![
            format!("{} / {}", bytes(s.memory.used), bytes(s.memory.total)),
            format!("Available {}", bytes(s.memory.available)),
            format!("Pressure {}", s.memory.pressure.as_deref().unwrap_or("N/A")),
            format!(
                "Swap {} | comp {}",
                bytes(s.memory.swap_used),
                s.memory
                    .compressed
                    .map(bytes)
                    .unwrap_or_else(|| "N/A".into())
            ),
            format!(
                "Swap in/out {} / {} KiB/s",
                rate(s.memory.swap_in_bps),
                rate(s.memory.swap_out_bps)
            ),
        ],
        GREEN,
    );
    card(
        frame,
        cards[3],
        " vLLM / optional loopback scrape ",
        vec![
            format!(
                "Running {} | queue {}",
                number(s.inference.running, ""),
                number(s.inference.waiting, "")
            ),
            format!("KV {} (max engine)", number(s.inference.kv_percent, "%")),
            format!(
                "Prompt {} | gen {} tok/s",
                number(s.inference.prompt_tps, ""),
                number(s.inference.generation_tps, "")
            ),
            format!(
                "Mean TTFT {}",
                number(s.inference.ttft_seconds.map(|s| s * 1000.0), " ms")
            ),
            format!(
                "Mean TPOT {}",
                number(s.inference.tpot_seconds.map(|s| s * 1000.0), " ms")
            ),
        ],
        CYAN,
    );
    let histories = Layout::horizontal([Constraint::Percentage(50); 2]).split(sections[1]);
    let cpu: Vec<u64> = view.cpu_history.iter().copied().collect();
    let gpu: Vec<u64> = view.gpu_history.iter().copied().collect();
    frame.render_widget(
        Sparkline::default()
            .block(block(" CPU % / last 120 samples "))
            .data(&cpu)
            .max(100)
            .style(Style::default().fg(GREEN)),
        histories[0],
    );
    frame.render_widget(
        Sparkline::default()
            .block(block(" GPU active % / consecutive valid samples "))
            .data(&gpu)
            .max(100)
            .style(Style::default().fg(CYAN)),
        histories[1],
    );
    let columns = Layout::horizontal([Constraint::Percentage(43), Constraint::Percentage(57)])
        .split(sections[2]);
    let io = Layout::vertical([Constraint::Percentage(50); 2]).split(columns[0]);
    let rows = s.disks.iter().map(|d| {
        Row::new([
            d.mount.clone(),
            bytes(d.available),
            rate(d.read_bps),
            rate(d.write_bps),
        ])
    });
    frame.render_widget(
        Table::new(
            rows,
            [
                Constraint::Min(10),
                Constraint::Length(9),
                Constraint::Length(7),
                Constraint::Length(7),
            ],
        )
        .header(Row::new(["Mount", "Free", "R KiB/s", "W KiB/s"]).style(Style::default().fg(CYAN)))
        .block(block(" Disk / APFS rows may share physical counters ")),
        io[0],
    );
    let rows = s.networks.iter().map(|n| {
        Row::new([
            n.name.clone(),
            rate(n.rx_bps),
            rate(n.tx_bps),
            n.errors.to_string(),
        ])
    });
    frame.render_widget(
        Table::new(
            rows,
            [
                Constraint::Min(10),
                Constraint::Length(8),
                Constraint::Length(8),
                Constraint::Length(6),
            ],
        )
        .header(
            Row::new(["Interface", "RX KiB/s", "TX KiB/s", "Errors"])
                .style(Style::default().fg(CYAN)),
        )
        .block(block(" Network / includes lo0; do not sum layers ")),
        io[1],
    );
    let mut processes: Vec<&Process> = s
        .processes
        .iter()
        .filter(|p| !view.focus || p.candidate)
        .collect();
    if view.memory_sort {
        processes.sort_by_key(|p| std::cmp::Reverse(p.memory));
    }
    let rows = processes.iter().map(|p| {
        Row::new([
            format!("{}{}", if p.candidate { "*" } else { "" }, p.pid),
            p.name.clone(),
            number(p.cpu_percent, ""),
            bytes(p.memory),
            rate(p.read_bps),
            rate(p.write_bps),
        ])
    });
    frame.render_widget(
        Table::new(
            rows,
            [
                Constraint::Length(7),
                Constraint::Min(10),
                Constraint::Length(7),
                Constraint::Length(9),
                Constraint::Length(7),
                Constraint::Length(7),
            ],
        )
        .header(
            Row::new(["PID *", "Process", "CPU%", "RSS", "R KiB/s", "W KiB/s"])
                .style(Style::default().fg(CYAN)),
        )
        .block(block(if view.focus {
            " Candidate names / f: all / m: sort "
        } else {
            " Processes / 100%=one core / *name match, not detection "
        })),
        columns[1],
    );
    frame.render_widget(
        Paragraph::new(
            s.hints
                .iter()
                .map(|s| Line::from(format!("- {s}")))
                .collect::<Vec<_>>(),
        )
        .block(block(
            " Bottleneck signals / heuristics, not a diagnosis / Tab: full context ",
        ))
        .style(Style::default().fg(Color::Rgb(232, 196, 130)))
        .wrap(Wrap { trim: false }),
        sections[3],
    );
}

fn details(frame: &mut Frame, area: Rect, s: &Snapshot, view: &View) {
    let mut lines = vec![
        "SOURCES / scope / limitations".into(), "".into(),
        "CPU: sysinfo Mach ticks, averaged over logical CPUs. Per-process 100%=one CPU; can exceed 100%.".into(),
        format!("Per-core busy%: {}", s.cores.iter().map(|v| format!("{v:.0}")).collect::<Vec<_>>().join("  ")),
        format!("GPU: {}", s.gpu.reason),
        "GPU covers the whole machine, including WindowServer and other apps. No per-PID GPU attribution.".into(),
        "Apple unified memory is shared by CPU/GPU; RSS + GPU allocations must NOT be added as dedicated VRAM.".into(),
        "Memory: sysinfo + kern.memorystatus_vm_pressure_level + Mach VM64. Compression is physical compressor bytes.".into(),
        format!("Memory source status: {}", if s.memory.native_reason.is_empty() { "available" } else { &s.memory.native_reason }),
        "Disk: sysinfo mount capacity + IOKit ancestor device bytes. APFS sibling volumes can duplicate counters.".into(),
        "Disk N/A = baseline pending, reset, or no nonzero device counters exposed. No device latency/queue/busy% is measured.".into(),
        "Network: sysinfo per-interface cumulative byte deltas, actual monotonic elapsed time. lo0 is local traffic.".into(),
        "VPN/physical/bridge counters may overlap. Throughput alone does not prove network saturation.".into(),
        "Processes: sysinfo names/CPU/RSS/rusage only; never read command lines, environments, prompts or credentials.".into(),
        "* means selected PID or candidate name substring; python may be unrelated to inference. Use --pid to narrow.".into(),
        "Only top 40 CPU processes plus candidates are retained (snapshot bound 160). m sorts the retained rows, not all system processes.".into(),
        format!("vLLM: {}", s.inference.reason),
        format!("Interval mean TTFT {} | TPOT {} | ITL {}", number(s.inference.ttft_seconds.map(|s| s * 1000.0), " ms"), number(s.inference.tpot_seconds.map(|s| s * 1000.0), " ms"), number(s.inference.itl_seconds.map(|s| s * 1000.0), " ms")),
        "vLLM latency values are interval histogram MEANS, not p95/p99. New/reset series and first scrapes show N/A.".into(),
        "Sampling window includes the requested native waiting interval and HTTP/OS collection; it is not CPU overhead.".into(),
        "Process I/O is N/A until nonzero lifetime counters are visible; inaccessible and never-used counters cannot be distinguished.".into(),
        "No inference server is started. Apple GPU inference needs an actual Metal-compatible backend (e.g. vLLM-Metal).".into(),
        "Missing vs zero: N/A is not idle. Old snapshots remain visible with age; paused sampling view is explicitly marked.".into(),
        "GPU active + low tok/s cannot distinguish compute, memory bandwidth, quantization or kernel inefficiency.".into(),
        "Next evidence: compare fixed model/context/batch experiments; use Metal System Trace/Instruments for GPU timeline.".into(),
        "Thermal sensors are observations only: this tool does not claim measured thermal throttling.".into(),
        "".into(), "CURRENT SIGNALS".into(),
    ];
    lines.extend(s.hints.iter().map(|s| format!("- {s}")));
    lines.extend(["".into(), "FILESYSTEMS (full list)".into()]);
    lines.extend(s.disks.iter().map(|d| {
        format!(
            "{} [{}] free {} / {}  read {} write {} KiB/s",
            d.mount,
            d.device,
            bytes(d.available),
            bytes(d.total),
            rate(d.read_bps),
            rate(d.write_bps)
        )
    }));
    lines.extend(["".into(), "NETWORK INTERFACES (full list)".into()]);
    lines.extend(s.networks.iter().map(|n| {
        format!(
            "{} RX {} TX {} KiB/s errors {}",
            n.name,
            rate(n.rx_bps),
            rate(n.tx_bps),
            n.errors
        )
    }));
    frame.render_widget(
        Paragraph::new(Text::from(
            lines.into_iter().map(Line::from).collect::<Vec<_>>(),
        ))
        .block(block(" Details / j,k or arrows to scroll "))
        .wrap(Wrap { trim: false })
        .scroll((view.scroll, 0)),
        area,
    );
}

#[cfg(test)]
mod tests {
    use super::*;
    use ratatui::{backend::TestBackend, Terminal};
    use std::time::Instant;

    #[test]
    fn rates_are_numeric_kib_per_second_not_double_scaled() {
        assert_eq!(rate(Some(2048.0)), "2.0");
        assert_eq!(rate(Some(0.0)), "0.0");
        assert_eq!(rate(None), "N/A");
    }

    #[test]
    fn layouts_and_missing_values_render_without_panics() {
        let completed = Completed {
            sample: Snapshot {
                sequence: 1,
                cpu_model: "Synthetic fixture".into(),
                ..Default::default()
            },
            at: Instant::now(),
        };
        for (width, height) in [(20, 5), (80, 24), (90, 30), (140, 45)] {
            let mut terminal = Terminal::new(TestBackend::new(width, height)).unwrap();
            for details in [false, true] {
                let mut view = View {
                    details,
                    ..Default::default()
                };
                view.observe(&completed.sample);
                terminal
                    .draw(|f| draw(f, Some(&completed), None, &view))
                    .unwrap();
                let text = terminal
                    .backend()
                    .buffer()
                    .content
                    .iter()
                    .map(|c| c.symbol())
                    .collect::<String>();
                assert!(text.contains("MAC LENS"));
                assert!(text.contains("N/A"));
                terminal
                    .draw(|f| draw(f, None, Some("synthetic failure"), &view))
                    .unwrap();
            }
        }
    }

    #[test]
    fn history_is_bounded_and_missing_gpu_is_not_zero() {
        let mut view = View::default();
        let mut s = Snapshot::default();
        s.gpu.active_percent = Some(20.0);
        for sequence in 1..300 {
            s.sequence = sequence;
            view.observe(&s);
        }
        assert_eq!(view.cpu_history.len(), 120);
        s.sequence += 1;
        s.gpu.active_percent = None;
        view.observe(&s);
        assert!(view.gpu_history.is_empty());
    }
}
