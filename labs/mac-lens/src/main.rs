use crossterm::event::{self, Event, KeyCode, KeyEventKind, KeyModifiers};
use mac_lens::collect::{Completed, Config, Worker};
use mac_lens::{inference, ui};
use std::io::{self, IsTerminal, Write};
use std::time::{Duration, Instant};

struct Options {
    config: Config,
    snapshot: bool,
    samples: u32,
}

fn options(args: impl IntoIterator<Item = String>) -> Result<Option<Options>, String> {
    let mut options = Options {
        config: Config::default(),
        snapshot: false,
        samples: 2,
    };
    let mut args = args.into_iter();
    let mut samples_given = false;
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--help" | "-h" => {
                println!("mac-lens / read-only macOS inference monitor\n\nUsage: mac-lens [--interval-ms 1000] [--no-gpu]\n       mac-lens --snapshot [--samples 2]\n\n--metrics-url http://127.0.0.1:8000/metrics   Optional local vLLM Prometheus reader\n--process vllm,python,ollama,llama,mlx        Candidate name substrings (not detection)\n--pid PID                                  Mark one process instead of name matches\n--interval-ms 500..5000                     Collection interval; native/HTTP costs may add time\n--no-gpu                                   Disable Apple native GPU collection\n--snapshot --samples 1..120                 JSON Lines to stdout; may contain local process names\n\nTUI: q/Ctrl-C quit; Space pause; Tab/1/2 pages; f candidates; m CPU/RAM sort; j/k details scroll.\nNo sudo, server startup, benchmarks, proxy use, credentials or automatic file exports.");
                return Ok(None);
            }
            "--snapshot" => options.snapshot = true,
            "--no-gpu" => options.config.gpu = false,
            "--interval-ms" => {
                let value = args
                    .next()
                    .ok_or("missing interval")?
                    .parse::<u64>()
                    .map_err(|_| "invalid interval")?;
                if !(500..=5000).contains(&value) {
                    return Err("interval must be 500..5000ms".into());
                }
                options.config.interval = Duration::from_millis(value);
            }
            "--samples" => {
                options.samples = args
                    .next()
                    .ok_or("missing samples")?
                    .parse()
                    .map_err(|_| "invalid samples")?;
                if !(1..=120).contains(&options.samples) {
                    return Err("samples must be 1..120".into());
                }
                samples_given = true;
            }
            "--pid" => {
                let pid = args
                    .next()
                    .ok_or("missing PID")?
                    .parse::<u32>()
                    .map_err(|_| "invalid PID")?;
                if pid == 0 {
                    return Err("PID must be positive".into());
                }
                options.config.pid = Some(pid);
            }
            "--process" => {
                let filter = args.next().ok_or("missing process filter")?;
                if filter.len() > 200 || filter.split(',').all(|s| s.trim().is_empty()) {
                    return Err("process filter must be nonempty and <=200 bytes".into());
                }
                options.config.process_filter = filter;
            }
            "--metrics-url" => {
                let url = args.next().ok_or("missing metrics URL")?;
                inference::validate_url(&url)?;
                options.config.metrics_url = Some(url);
            }
            _ => return Err("unknown argument; use --help".into()),
        }
    }
    if samples_given && !options.snapshot {
        return Err("--samples requires --snapshot".into());
    }
    Ok(Some(options))
}

fn snapshots(options: &Options) -> Result<(), Box<dyn std::error::Error>> {
    let worker = Worker::start(options.config.clone());
    let mut previous = 0;
    let mut emitted = 0;
    let mut deadline = Instant::now() + Duration::from_secs(30);
    let stdout = io::stdout();
    let mut output = stdout.lock();
    while emitted < options.samples {
        let latest = worker.latest.lock().map_err(|_| "snapshot lock poisoned")?;
        if let Some(error) = &latest.error {
            return Err(error.clone().into());
        }
        if let Some(completed) = &latest.completed {
            if completed.sample.sequence != previous {
                serde_json::to_writer(&mut output, &completed.sample)?;
                writeln!(output)?;
                output.flush()?;
                previous = completed.sample.sequence;
                emitted += 1;
                deadline = Instant::now() + Duration::from_secs(30);
            }
        }
        drop(latest);
        if Instant::now() > deadline {
            return Err("sampler produced no snapshot for 30s".into());
        }
        std::thread::sleep(Duration::from_millis(30));
    }
    Ok(())
}

fn tui(config: Config) -> Result<(), Box<dyn std::error::Error>> {
    if !io::stdout().is_terminal() || !io::stdin().is_terminal() {
        return Err("TUI requires an interactive terminal; use --snapshot for JSON Lines".into());
    }
    struct Restore;
    impl Drop for Restore {
        fn drop(&mut self) {
            ratatui::restore();
        }
    }
    let _restore = Restore;
    let mut terminal = ratatui::try_init()?;
    let worker = Worker::start(config);
    let mut view = ui::View::default();
    let mut displayed: Option<Completed> = None;
    loop {
        let latest = worker.latest.lock().map_err(|_| "snapshot lock poisoned")?;
        let error = latest.error.clone();
        if let Some(reason) = &error {
            return Err(reason.clone().into());
        }
        if !view.paused {
            if let Some(completed) = &latest.completed {
                view.observe(&completed.sample);
                displayed = Some(completed.clone());
            }
        }
        drop(latest);
        terminal.draw(|frame| ui::draw(frame, displayed.as_ref(), error.as_deref(), &view))?;
        if !event::poll(Duration::from_millis(100))? {
            continue;
        }
        if let Event::Key(key) = event::read()? {
            if key.kind != KeyEventKind::Press {
                continue;
            }
            if key.code == KeyCode::Char('q')
                || (key.code == KeyCode::Char('c') && key.modifiers.contains(KeyModifiers::CONTROL))
            {
                break;
            }
            match key.code {
                KeyCode::Char(' ') => view.paused = !view.paused,
                KeyCode::Tab => {
                    view.details = !view.details;
                    view.scroll = 0;
                }
                KeyCode::Char('1') => view.details = false,
                KeyCode::Char('2') => view.details = true,
                KeyCode::Char('f') => view.focus = !view.focus,
                KeyCode::Char('m') => view.memory_sort = !view.memory_sort,
                KeyCode::Down | KeyCode::Char('j') => {
                    view.scroll = view.scroll.saturating_add(1).min(2000)
                }
                KeyCode::Up | KeyCode::Char('k') => view.scroll = view.scroll.saturating_sub(1),
                _ => {}
            }
        }
    }
    Ok(())
}

fn main() {
    let result = (|| -> Result<(), Box<dyn std::error::Error>> {
        let Some(options) = options(std::env::args().skip(1)).map_err(io::Error::other)? else {
            return Ok(());
        };
        if options.snapshot {
            snapshots(&options)
        } else {
            tui(options.config)
        }
    })();
    if let Err(error) = result {
        eprintln!("mac-lens: {error}");
        std::process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cli_rejects_unsafe_or_ambiguous_options() {
        for args in [
            vec!["--samples", "2"],
            vec!["--interval-ms", "0"],
            vec!["--pid", "0"],
            vec!["--process", ""],
            vec!["--snapshot", "--samples", "0"],
            vec!["--metrics-url", "http://example.com/metrics"],
            vec!["--unknown"],
        ] {
            assert!(options(args.into_iter().map(str::to_owned)).is_err());
        }
        assert!(options(
            ["--snapshot", "--samples", "2", "--no-gpu"]
                .into_iter()
                .map(str::to_owned)
        )
        .unwrap()
        .is_some());
    }
}
