use crate::inference::Reader;
use crate::model::{self, Disk, Memory, Network, Process, Rates, Snapshot};
use crate::native::{self, GpuSampler};
use std::collections::HashSet;
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc, Mutex,
};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use sysinfo::{
    CpuRefreshKind, Disks, Networks, ProcessRefreshKind, ProcessesToUpdate, RefreshKind, System,
};

#[derive(Clone)]
pub struct Config {
    pub interval: Duration,
    pub gpu: bool,
    pub metrics_url: Option<String>,
    pub process_filter: String,
    pub pid: Option<u32>,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            interval: Duration::from_secs(1),
            gpu: true,
            metrics_url: None,
            process_filter: "vllm,python,ollama,llama,mlx".into(),
            pid: None,
        }
    }
}

#[derive(Clone)]
pub struct Completed {
    pub sample: Snapshot,
    pub at: Instant,
}

#[derive(Default)]
pub struct Latest {
    pub completed: Option<Completed>,
    pub error: Option<String>,
}

pub struct Worker {
    pub latest: Arc<Mutex<Latest>>,
    stop: Arc<AtomicBool>,
}

impl Worker {
    pub fn start(config: Config) -> Self {
        let latest = Arc::new(Mutex::new(Latest::default()));
        let stop = Arc::new(AtomicBool::new(false));
        let (shared, stopping) = (latest.clone(), stop.clone());
        std::thread::spawn(move || {
            let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
                let mut collector = Collector::new(config)?;
                while !stopping.load(Ordering::Relaxed) {
                    let sample = collector.sample();
                    if let Ok(mut latest) = shared.lock() {
                        // One latest snapshot, not an unbounded sample queue.
                        latest.completed = Some(Completed {
                            sample,
                            at: Instant::now(),
                        });
                    }
                }
                Ok::<(), String>(())
            }));
            let reason = match result {
                Ok(Ok(())) => return,
                Ok(Err(e)) => e,
                Err(_) => "Sampler thread panicked; displayed snapshot is stale".into(),
            };
            if let Ok(mut latest) = shared.lock() {
                latest.error = Some(reason);
            }
        });
        Self { latest, stop }
    }
}

impl Drop for Worker {
    fn drop(&mut self) {
        // Do not block terminal restoration on a slow native collection call.
        // No workloads are launched. macmon may invoke system_profiler on init.
        // Process exit releases native resources.
        self.stop.store(true, Ordering::Relaxed);
    }
}

struct Collector {
    config: Config,
    system: System,
    networks: Networks,
    disks: Disks,
    rates: Rates,
    gpu: GpuSampler,
    inference: Reader,
    previous_processes: HashSet<(u32, u64)>,
    sequence: u64,
}

impl Collector {
    fn new(config: Config) -> Result<Self, String> {
        let mut system = System::new_with_specifics(
            RefreshKind::nothing().with_cpu(CpuRefreshKind::everything()),
        );
        system.refresh_processes_specifics(ProcessesToUpdate::All, true, process_refresh());
        let gpu = GpuSampler::new(config.gpu);
        let inference = Reader::new(config.metrics_url.clone())?;
        let previous_processes = system
            .processes()
            .iter()
            .map(|(pid, p)| (pid.as_u32(), p.start_time()))
            .collect();
        Ok(Self {
            config,
            system,
            gpu,
            inference,
            previous_processes,
            networks: Networks::new_with_refreshed_list(),
            disks: Disks::new_with_refreshed_list(),
            rates: Rates::default(),
            sequence: 0,
        })
    }

    fn sample(&mut self) -> Snapshot {
        let began = Instant::now();
        let gpu = self.gpu.sample(self.config.interval);
        self.system.refresh_cpu_usage();
        self.system.refresh_memory();
        self.system
            .refresh_processes_specifics(ProcessesToUpdate::All, true, process_refresh());
        let process_at = Instant::now();
        self.networks.refresh(true);
        let network_at = Instant::now();
        self.disks.refresh(true);
        let disk_at = Instant::now();
        let vm = native::vm();
        let vm_at = Instant::now();
        let mut memory = Memory {
            total: self.system.total_memory(),
            used: self.system.used_memory(),
            available: self.system.available_memory(),
            swap_used: self.system.used_swap(),
            swap_total: self.system.total_swap(),
            pressure: vm.pressure,
            compressed: vm.compressed,
            native_reason: vm.reason,
            ..Default::default()
        };
        memory.swap_in_bps = vm
            .swap_in_bytes
            .and_then(|n| self.rates.observe("vm:in", n as f64, vm_at));
        memory.swap_out_bps = vm
            .swap_out_bytes
            .and_then(|n| self.rates.observe("vm:out", n as f64, vm_at));
        if vm.swap_in_bytes.is_none() || vm.swap_out_bytes.is_none() {
            self.rates.retain("vm:", &HashSet::new());
        }
        let mut present = HashSet::new();
        let mut networks: Vec<_> = self
            .networks
            .iter()
            .map(|(name, n)| {
                let rx = format!("net:{name}:rx");
                let tx = format!("net:{name}:tx");
                present.extend([rx.clone(), tx.clone()]);
                Network {
                    name: model::safe_text(name),
                    rx_bps: self
                        .rates
                        .observe(&rx, n.total_received() as f64, network_at),
                    tx_bps: self
                        .rates
                        .observe(&tx, n.total_transmitted() as f64, network_at),
                    errors: n
                        .total_errors_on_received()
                        .saturating_add(n.total_errors_on_transmitted()),
                }
            })
            .collect();
        self.rates.retain("net:", &present);
        networks.sort_by(|a, b| {
            let av = a.rx_bps.unwrap_or(0.0) + a.tx_bps.unwrap_or(0.0);
            let bv = b.rx_bps.unwrap_or(0.0) + b.tx_bps.unwrap_or(0.0);
            bv.total_cmp(&av).then(a.name.cmp(&b.name))
        });
        present.clear();
        let mut disks = Vec::new();
        for d in &self.disks {
            let device = d.name().to_string_lossy();
            let mount = d.mount_point().to_string_lossy();
            // APFS volumes may share the same physical counters. Keep per-mount
            // rows, never sum them into a fictitious device throughput.
            let read = format!("disk:{device}:{mount}:read");
            let write = format!("disk:{device}:{mount}:write");
            let usage = d.usage();
            let available = usage.total_read_bytes != 0 || usage.total_written_bytes != 0;
            let (read_bps, write_bps) = if available {
                present.extend([read.clone(), write.clone()]);
                (
                    self.rates
                        .observe(&read, usage.total_read_bytes as f64, disk_at),
                    self.rates
                        .observe(&write, usage.total_written_bytes as f64, disk_at),
                )
            } else {
                (None, None)
            };
            disks.push(Disk {
                device: model::safe_text(&device),
                mount: model::safe_text(&mount),
                total: d.total_space(),
                available: d.available_space(),
                read_bps,
                write_bps,
            });
        }
        self.rates.retain("disk:", &present);
        disks.sort_by(|a, b| a.mount.cmp(&b.mount));
        present.clear();
        let mut next_processes = HashSet::new();
        let filters: Vec<_> = self
            .config
            .process_filter
            .split(',')
            .map(|s| s.trim().to_lowercase())
            .filter(|s| !s.is_empty())
            .collect();
        let mut processes = Vec::new();
        for (pid, p) in self.system.processes() {
            let id = pid.as_u32();
            let identity = (id, p.start_time());
            next_processes.insert(identity);
            let name = p.name().to_string_lossy();
            let candidate = self.config.pid.map_or_else(
                || filters.iter().any(|f| name.to_lowercase().contains(f)),
                |selected| id == selected,
            );
            let usage = p.disk_usage();
            let read = format!("proc:{id}:{}:read", p.start_time());
            let write = format!("proc:{id}:{}:write", p.start_time());
            // sysinfo uses zero when rusage is unavailable (e.g. SIP). With no
            // nonzero lifetime counter, idle and inaccessible are ambiguous.
            let (read_bps, write_bps) =
                if usage.total_read_bytes != 0 || usage.total_written_bytes != 0 {
                    present.extend([read.clone(), write.clone()]);
                    (
                        self.rates
                            .observe(&read, usage.total_read_bytes as f64, process_at),
                        self.rates
                            .observe(&write, usage.total_written_bytes as f64, process_at),
                    )
                } else {
                    (None, None)
                };
            processes.push(Process {
                pid: id,
                name: model::safe_text(&name),
                cpu_percent: self
                    .previous_processes
                    .contains(&identity)
                    .then(|| {
                        model::finite(
                            f64::from(p.cpu_usage()),
                            0.0,
                            100.0 * self.system.cpus().len() as f64,
                        )
                    })
                    .flatten(),
                memory: p.memory(),
                candidate,
                read_bps,
                write_bps,
            });
        }
        self.previous_processes = next_processes;
        self.rates.retain("proc:", &present);
        processes.sort_by(|a, b| {
            b.cpu_percent
                .unwrap_or(0.0)
                .total_cmp(&a.cpu_percent.unwrap_or(0.0))
                .then(a.pid.cmp(&b.pid))
        });
        // Retain candidates even when idle; bound snapshot/UI cost on large hosts.
        let processes = processes
            .into_iter()
            .enumerate()
            .filter(|(i, p)| *i < 40 || p.candidate)
            .map(|(_, p)| p)
            .take(160)
            .collect();
        self.sequence += 1;
        let mut snapshot = Snapshot {
            schema_version: 1,
            sequence: self.sequence,
            unix_ms: 0,
            sampling_ms: 0,
            cpu_model: self
                .system
                .cpus()
                .first()
                .map(|c| model::safe_text(c.brand()))
                .unwrap_or_default(),
            cpu_percent: f64::from(self.system.global_cpu_usage()),
            cores: self
                .system
                .cpus()
                .iter()
                .map(|c| f64::from(c.cpu_usage()))
                .collect(),
            load_one: System::load_average().one,
            gpu,
            memory,
            disks,
            networks,
            processes,
            inference: self.inference.sample(),
            hints: Vec::new(),
        };
        snapshot.unix_ms = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_millis();
        snapshot.sampling_ms = began.elapsed().as_millis();
        snapshot.hints = model::hints(&snapshot);
        snapshot
    }
}

fn process_refresh() -> ProcessRefreshKind {
    // Deliberately omit cmdline, environment, cwd, executable and user IDs.
    ProcessRefreshKind::nothing()
        .with_cpu()
        .with_memory()
        .with_disk_usage()
}
