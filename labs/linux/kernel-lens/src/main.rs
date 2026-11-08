use crossterm::event::{self, Event, KeyCode, KeyEventKind, KeyModifiers};
use crossterm::execute;
use crossterm::terminal::{
    disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen,
};
use kernel_lens::bench::{self, Config, Kind, Session};
use kernel_lens::collectors::Kernel;
use kernel_lens::model::Topic;
use kernel_lens::ui::{self, View};
use ratatui::backend::CrosstermBackend;
use ratatui::Terminal;
use std::io::{self, IsTerminal, Write};
use std::time::{Duration, Instant};

enum Action {
    Tui,
    Snapshot,
    Summary,
    Benchmark(Kind),
    Worker(Kind),
}
struct Options {
    action: Action,
    samples: usize,
    interval: Duration,
    bench: Config,
}
fn number<T: std::str::FromStr>(
    args: &mut impl Iterator<Item = String>,
    name: &str,
) -> Result<T, String> {
    args.next()
        .ok_or_else(|| format!("missing {name} value"))?
        .parse()
        .map_err(|_| format!("invalid {name}"))
}
fn options() -> Result<Option<Options>, String> {
    let mut result = Options {
        action: Action::Tui,
        samples: 2,
        interval: Duration::from_secs(1),
        bench: Config::default(),
    };
    let mut args = std::env::args().skip(1);
    let mut actions = 0;
    let mut samples_given = false;
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--help" | "-h" => {
                println!("kernel-lens — Linux/container overview and selected benchmarks\n\nUsage: kernel-lens [--interval-ms 1000] [benchmark options]\n       kernel-lens --summary\n       kernel-lens --snapshot [--samples 2] [--interval-ms 1000]\n       kernel-lens --benchmark KIND [benchmark options]\n\nKIND: cpu, memory, scheduler, tcp-loopback, file-io\n--bench-duration-ms  100..2000 per round (default 250; not used by file-io)\n--bench-rounds       1..7 (default 3)\n--bench-size-mib     1..64 (default 8; memory buffer/file size)\n--bench-dir          Existing directory, required for file-io\n\nBenchmarks run only after selection. CLI emits JSON with round results and environment.\nUse a release build for comparisons. TUI: 1–9 topics, Space selects benchmark, r runs, c cancels.\nNo privilege changes, raw block access, external network traffic or BPF loading.");
                return Ok(None);
            }
            "--summary" => {
                result.action = Action::Summary;
                actions += 1;
            }
            "--snapshot" => {
                result.action = Action::Snapshot;
                actions += 1;
            }
            "--benchmark" | "--bench-worker" => {
                let kind = Kind::parse(&args.next().ok_or("missing benchmark kind")?)?;
                result.action = if arg == "--bench-worker" {
                    Action::Worker(kind)
                } else {
                    Action::Benchmark(kind)
                };
                actions += 1;
            }
            "--samples" => {
                samples_given = true;
                result.samples = number(&mut args, "--samples")?;
            }
            "--interval-ms" => {
                let ms = number(&mut args, "--interval-ms")?;
                if !(200..=60000).contains(&ms) {
                    return Err("--interval-ms must be 200..60000".into());
                }
                result.interval = Duration::from_millis(ms);
            }
            "--bench-duration-ms" => {
                result.bench.duration_ms = number(&mut args, "--bench-duration-ms")?
            }
            "--bench-rounds" => result.bench.rounds = number(&mut args, "--bench-rounds")?,
            "--bench-size-mib" => result.bench.size_mib = number(&mut args, "--bench-size-mib")?,
            "--bench-dir" => {
                result.bench.directory = Some(args.next().ok_or("missing --bench-dir")?.into())
            }
            _ => return Err(format!("unknown argument: {arg}; use --help")),
        }
    }
    if actions > 1 {
        return Err("choose only one of --summary, --snapshot or --benchmark".into());
    }
    if samples_given && !matches!(result.action, Action::Snapshot) {
        return Err("--samples requires --snapshot".into());
    }
    if !(1..=100000).contains(&result.samples) {
        return Err("--samples must be 1..100000".into());
    }
    result.bench.validate(Kind::Cpu)?;
    Ok(Some(result))
}

struct Screen;
impl Drop for Screen {
    fn drop(&mut self) {
        let _ = disable_raw_mode();
        let _ = execute!(io::stdout(), LeaveAlternateScreen, crossterm::cursor::Show);
    }
}
fn run(options: Options) -> Result<(), Box<dyn std::error::Error>> {
    if !cfg!(target_os = "linux") {
        return Err("kernel-lens requires Linux /proc and /sys".into());
    }
    match options.action {
        Action::Benchmark(kind) => {
            let mut runner = bench::Runner::start(kind, &options.bench)?;
            loop {
                if let Some(result) = runner.poll() {
                    serde_json::to_writer(io::stdout().lock(), &result?)?;
                    println!();
                    return Ok(());
                }
                std::thread::sleep(Duration::from_millis(25));
            }
        }
        Action::Worker(kind) => {
            let report = bench::execute(kind, options.bench)?;
            let output = serde_json::to_vec(&report)?;
            if output.len() > 32768 {
                return Err("benchmark report exceeds 32 KiB".into());
            }
            io::stdout().write_all(&output)?;
            return Ok(());
        }
        _ => {}
    }
    let mut kernel = Kernel::live();
    if matches!(options.action, Action::Summary) {
        let snapshot = kernel.sample();
        for metric in snapshot
            .metrics
            .iter()
            .filter(|m| m.topic == Topic::Summary)
        {
            println!(
                "{}: {} {} [{}]",
                metric.name, metric.value, metric.unit, metric.scope
            );
        }
        return Ok(());
    }
    if matches!(options.action, Action::Snapshot) {
        let mut stdout = io::stdout().lock();
        for index in 0..options.samples {
            if index > 0 {
                std::thread::sleep(options.interval);
            }
            serde_json::to_writer(&mut stdout, &kernel.sample())?;
            writeln!(stdout)?;
            stdout.flush()?;
        }
        return Ok(());
    }
    if !io::stdin().is_terminal() || !io::stdout().is_terminal() {
        return Err("TUI needs an interactive terminal; use --summary or --snapshot".into());
    }
    enable_raw_mode()?;
    let _screen = Screen;
    execute!(io::stdout(), EnterAlternateScreen)?;
    let mut terminal = Terminal::new(CrosstermBackend::new(io::stdout()))?;
    terminal.hide_cursor()?;
    let mut view = View::default();
    let mut session = Session::new(options.bench);
    let mut snapshot = kernel.sample();
    let mut sampled_at = Instant::now();
    loop {
        session.poll();
        if !view.paused && sampled_at.elapsed() >= options.interval {
            snapshot = kernel.sample();
            sampled_at = Instant::now();
        }
        terminal.draw(|frame| {
            ui::draw(
                frame,
                &snapshot,
                &view,
                sampled_at.elapsed().as_secs_f64(),
                &session,
            )
        })?;
        if !event::poll(Duration::from_millis(100))? {
            continue;
        }
        let Event::Key(key) = event::read()? else {
            continue;
        };
        if key.kind == KeyEventKind::Release {
            continue;
        }
        if key.code == KeyCode::Char('c') && key.modifiers.contains(KeyModifiers::CONTROL) {
            break;
        }
        if view.searching {
            match key.code {
                KeyCode::Esc => {
                    view.searching = false;
                    view.filter.clear();
                }
                KeyCode::Enter => view.searching = false,
                KeyCode::Backspace => {
                    view.filter.pop();
                }
                KeyCode::Char(c) => view.filter.push(c),
                _ => {}
            }
            view.selected = 0;
            continue;
        }
        if Topic::ALL[view.tab] == Topic::Benchmark {
            match key.code {
                KeyCode::Enter => {
                    session.detail = !session.detail;
                    session.result_scroll = 0;
                    continue;
                }
                KeyCode::Esc if session.detail => {
                    session.detail = false;
                    session.result_scroll = 0;
                    continue;
                }
                KeyCode::PageDown => {
                    session.result_scroll = session.result_scroll.saturating_add(5).min(200);
                    continue;
                }
                KeyCode::PageUp => {
                    session.result_scroll = session.result_scroll.saturating_sub(5);
                    continue;
                }
                KeyCode::Char(' ') => {
                    session.selected[session.cursor] = !session.selected[session.cursor];
                    continue;
                }
                KeyCode::Char('r') => {
                    session.start_selected();
                    continue;
                }
                KeyCode::Char('c') => {
                    session.cancel();
                    continue;
                }
                KeyCode::Down | KeyCode::Char('j') => {
                    session.cursor = (session.cursor + 1).min(Kind::ALL.len() - 1);
                    continue;
                }
                KeyCode::Up | KeyCode::Char('k') => {
                    session.cursor = session.cursor.saturating_sub(1);
                    continue;
                }
                _ => {}
            }
        }
        if Topic::ALL[view.tab] == Topic::Summary && !view.detail {
            if key.code == KeyCode::Enter && !view.summary_table {
                view.summary_table = true;
                continue;
            }
            if key.code == KeyCode::Esc && view.summary_table {
                view.summary_table = false;
                continue;
            }
        }
        if view.detail {
            match key.code {
                KeyCode::Down | KeyCode::Char('j') => {
                    view.detail_scroll = view.detail_scroll.saturating_add(1).min(2000);
                    continue;
                }
                KeyCode::Up | KeyCode::Char('k') => {
                    view.detail_scroll = view.detail_scroll.saturating_sub(1);
                    continue;
                }
                KeyCode::PageDown => {
                    view.detail_scroll = view.detail_scroll.saturating_add(10).min(2000);
                    continue;
                }
                KeyCode::PageUp => {
                    view.detail_scroll = view.detail_scroll.saturating_sub(10);
                    continue;
                }
                KeyCode::Enter | KeyCode::Esc => {
                    view.detail = false;
                    view.detail_scroll = 0;
                    continue;
                }
                _ => {}
            }
        }
        let rows = view.row_count(&snapshot);
        match key.code {
            KeyCode::Char('q') => break,
            KeyCode::Enter => {
                view.detail = true;
                view.detail_scroll = 0;
            }
            KeyCode::Tab | KeyCode::Right => view.switch(view.tab + 1),
            KeyCode::BackTab | KeyCode::Left => {
                view.switch((view.tab + Topic::ALL.len() - 1) % Topic::ALL.len())
            }
            KeyCode::Char(c @ '1'..='9') => view.switch((c as u8 - b'1') as usize),
            KeyCode::Down | KeyCode::Char('j') => {
                view.selected = view.selected.saturating_add(1).min(rows.saturating_sub(1))
            }
            KeyCode::Up | KeyCode::Char('k') => view.selected = view.selected.saturating_sub(1),
            KeyCode::PageDown => {
                view.selected = view.selected.saturating_add(10).min(rows.saturating_sub(1))
            }
            KeyCode::PageUp => view.selected = view.selected.saturating_sub(10),
            KeyCode::Home => view.selected = 0,
            KeyCode::End => view.selected = rows.saturating_sub(1),
            KeyCode::Char(' ') => view.paused = !view.paused,
            KeyCode::Char('/') => view.searching = true,
            KeyCode::Char('?') => view.help = !view.help,
            KeyCode::Esc => {
                view.filter.clear();
                view.selected = 0;
            }
            _ => {}
        }
    }
    session.cancel();
    Ok(())
}
fn main() {
    let result = options()
        .map_err(|e| -> Box<dyn std::error::Error> { e.into() })
        .and_then(|options| options.map_or(Ok(()), run));
    if let Err(error) = result {
        eprintln!("kernel-lens: {error}");
        std::process::exit(1);
    }
}
