use crate::collectors::Kernel;
use crate::model::{Snapshot, Topic};
use serde::{Deserialize, Serialize};
use std::collections::VecDeque;
use std::fs::{File, OpenOptions};
use std::hint::black_box;
use std::io::{Read, Seek, SeekFrom, Write};
use std::net::{Shutdown, TcpListener, TcpStream};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::thread::JoinHandle;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Kind {
    Cpu,
    Memory,
    Scheduler,
    TcpLoopback,
    FileIo,
}
impl Kind {
    pub const ALL: [Self; 5] = [
        Self::Cpu,
        Self::Memory,
        Self::Scheduler,
        Self::TcpLoopback,
        Self::FileIo,
    ];
    pub fn id(self) -> &'static str {
        match self {
            Self::Cpu => "cpu",
            Self::Memory => "memory",
            Self::Scheduler => "scheduler",
            Self::TcpLoopback => "tcp-loopback",
            Self::FileIo => "file-io",
        }
    }
    pub fn parse(text: &str) -> Result<Self, String> {
        Self::ALL
            .into_iter()
            .find(|kind| kind.id() == text)
            .ok_or_else(|| format!("unknown benchmark {text}"))
    }
    pub fn label(self) -> &'static str {
        match self {
            Self::Cpu => "CPU · 单线程整数依赖链",
            Self::Memory => "内存 · 固定工作集拷贝",
            Self::Scheduler => "调度 · 两线程 channel 往返",
            Self::TcpLoopback => "网络 · TCP 回环吞吐",
            Self::FileIo => "存储 · 临时文件读写 + sync_data",
        }
    }
    pub fn explanation(self) -> &'static str {
        match self {
            Self::Cpu=>"一个线程反复运行固定 u64 混合运算链。M iterations/s 越高越好；不是跨算法通用 CPU 分数，线程未绑核。",
            Self::Memory=>"一个线程反复拷贝指定大小的预触页缓冲区。GiB/s 按拷贝有效字节计；工作集可能命中缓存，不等于 DRAM 峰值带宽。",
            Self::Scheduler=>"两个线程使用零容量 channel 同步请求/响应。µs/roundtrip 越低越好；包括锁、IPC 库及调度成本，不是纯内核调度延迟。",
            Self::TcpLoopback=>"在当前网络 namespace 的 127.0.0.1 临时端口传输。GiB/s 按服务端实际接收量计，只覆盖本机 TCP 栈，不经过物理网卡。",
            Self::FileIo=>"在显式指定目录中新建独占临时文件，计时写入 + sync_data，再读取。读取可能命中页缓存，不能当成裸盘或冷读性能；不清缓存、不操作块设备。",
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Config {
    pub duration_ms: u64,
    pub rounds: usize,
    pub size_mib: usize,
    pub directory: Option<PathBuf>,
}
impl Default for Config {
    fn default() -> Self {
        Self {
            duration_ms: 250,
            rounds: 3,
            size_mib: 8,
            directory: None,
        }
    }
}
impl Config {
    pub fn validate(&self, kind: Kind) -> Result<(), String> {
        if !(100..=2000).contains(&self.duration_ms) {
            return Err("--bench-duration-ms must be 100..2000".into());
        }
        if !(1..=7).contains(&self.rounds) {
            return Err("--bench-rounds must be 1..7".into());
        }
        if !(1..=64).contains(&self.size_mib) {
            return Err("--bench-size-mib must be 1..64".into());
        }
        if kind == Kind::FileIo {
            let directory = self
                .directory
                .as_ref()
                .ok_or("file-io requires --bench-dir pointing to an existing writable directory")?;
            if !directory.is_dir() {
                return Err("--bench-dir is not an existing directory".into());
            }
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Measurement {
    pub name: String,
    pub unit: String,
    pub values: Vec<f64>,
    pub median: f64,
    pub min: f64,
    pub max: f64,
}
impl Measurement {
    fn new(name: &str, unit: &str, values: Vec<f64>) -> Result<Self, String> {
        if values.is_empty() || values.iter().any(|n| !n.is_finite() || *n < 0.0) {
            return Err("invalid measurement samples".into());
        }
        let mut sorted = values.clone();
        sorted.sort_by(f64::total_cmp);
        let middle = sorted.len() / 2;
        let median = if sorted.len().is_multiple_of(2) {
            (sorted[middle - 1] + sorted[middle]) / 2.0
        } else {
            sorted[middle]
        };
        Ok(Self {
            name: name.into(),
            unit: unit.into(),
            median,
            min: sorted[0],
            max: sorted[sorted.len() - 1],
            values,
        })
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Observation {
    pub name: String,
    pub value: String,
    pub unit: String,
    pub scope: String,
}
fn observations(snapshot: &Snapshot) -> Vec<Observation> {
    snapshot
        .metrics
        .iter()
        .filter(|m| {
            m.name == "cpu busy"
                || m.name == "procs_running"
                || m.name == "procs_blocked"
                || m.name == "MemAvailable"
                || m.name.starts_with("load 1/5/15m")
                || m.name == "cpu.stat"
        })
        .take(20)
        .map(|m| Observation {
            name: m.name.clone(),
            value: m.value.clone(),
            unit: m.unit.clone(),
            scope: m.scope.clone(),
        })
        .collect()
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Report {
    pub schema_version: u32,
    pub kind: Kind,
    pub config: Config,
    pub started_unix_ms: u128,
    pub elapsed_ms: u128,
    pub build_mode: String,
    pub workload_version: u32,
    pub environment: Vec<(String, String)>,
    pub measurements: Vec<Measurement>,
    pub observations_before: Vec<Observation>,
    pub observations_after: Vec<Observation>,
    pub notes: Vec<String>,
}

fn cpu(duration: Duration) -> Result<Vec<(&'static str, &'static str, f64)>, String> {
    let start = Instant::now();
    let mut count = 0_u64;
    let mut x = black_box(1_u64);
    while start.elapsed() < duration {
        for _ in 0..4096 {
            x = x
                .wrapping_mul(6364136223846793005)
                .wrapping_add(1442695040888963407);
            x ^= x >> 17;
        }
        black_box(x);
        count += 4096;
    }
    Ok(vec![(
        "dependent integer chain",
        "M iterations/s",
        count as f64 / start.elapsed().as_secs_f64() / 1e6,
    )])
}
fn memory(
    duration: Duration,
    size: usize,
) -> Result<Vec<(&'static str, &'static str, f64)>, String> {
    let source = vec![0xa5_u8; size];
    let mut target = vec![0x5a_u8; size];
    // Touch both buffers before timing so allocation and initial faults are excluded.
    black_box(source.iter().fold(0_u8, |a, b| a ^ b));
    target.fill(0x33);
    let start = Instant::now();
    let mut copies = 0_u64;
    while start.elapsed() < duration {
        target.copy_from_slice(black_box(&source));
        black_box(&target);
        copies += 1;
    }
    Ok(vec![(
        "copy payload (not read+write traffic)",
        "GiB/s",
        copies as f64 * size as f64 / start.elapsed().as_secs_f64() / 1073741824.0,
    )])
}
fn scheduler(duration: Duration) -> Result<Vec<(&'static str, &'static str, f64)>, String> {
    let (request_tx, request_rx) = std::sync::mpsc::sync_channel::<()>(0);
    let (reply_tx, reply_rx) = std::sync::mpsc::sync_channel::<()>(0);
    let worker = std::thread::spawn(move || {
        while request_rx.recv().is_ok() {
            if reply_tx.send(()).is_err() {
                break;
            }
        }
    });
    for _ in 0..16 {
        request_tx.send(()).map_err(|e| e.to_string())?;
        reply_rx.recv().map_err(|e| e.to_string())?;
    }
    let start = Instant::now();
    let mut rounds = 0;
    while start.elapsed() < duration {
        request_tx.send(()).map_err(|e| e.to_string())?;
        reply_rx.recv().map_err(|e| e.to_string())?;
        rounds += 1;
    }
    let elapsed = start.elapsed();
    drop(request_tx);
    drop(reply_rx);
    worker.join().map_err(|_| "scheduler worker panicked")?;
    Ok(vec![(
        "channel request/reply mean",
        "µs/roundtrip",
        elapsed.as_secs_f64() * 1e6 / rounds as f64,
    )])
}
fn tcp(duration: Duration) -> Result<Vec<(&'static str, &'static str, f64)>, String> {
    let listener =
        TcpListener::bind((std::net::Ipv4Addr::LOCALHOST, 0)).map_err(|e| e.to_string())?;
    let address = listener.local_addr().map_err(|e| e.to_string())?;
    let mut client =
        TcpStream::connect_timeout(&address, Duration::from_secs(1)).map_err(|e| e.to_string())?;
    let (mut server, _) = listener.accept().map_err(|e| e.to_string())?;
    client
        .set_write_timeout(Some(Duration::from_secs(1)))
        .map_err(|e| e.to_string())?;
    server
        .set_read_timeout(Some(Duration::from_secs(2)))
        .map_err(|e| e.to_string())?;
    let worker = std::thread::spawn(move || -> Result<u64, String> {
        let mut buffer = [0_u8; 65536];
        let mut received = 0;
        loop {
            let n = server.read(&mut buffer).map_err(|e| e.to_string())?;
            if n == 0 {
                break;
            }
            received += n as u64;
        }
        Ok(received)
    });
    let buffer = [0xa5_u8; 65536];
    let start = Instant::now();
    let mut error = None;
    while start.elapsed() < duration {
        if let Err(e) = client.write_all(&buffer) {
            error = Some(e.to_string());
            break;
        }
    }
    let shutdown = client.shutdown(Shutdown::Write).map_err(|e| e.to_string());
    let received = worker.join().map_err(|_| "TCP receiver panicked")??;
    let elapsed = start.elapsed();
    shutdown?;
    if let Some(error) = error {
        return Err(error);
    }
    Ok(vec![(
        "TCP loopback received payload",
        "GiB/s",
        received as f64 / elapsed.as_secs_f64() / 1073741824.0,
    )])
}

struct Scratch {
    file: File,
    path: PathBuf,
}
impl Scratch {
    fn new(directory: &std::path::Path) -> Result<Self, String> {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_nanos();
        let path = directory.join(format!(
            ".kernel-lens-bench-{}-{unique}",
            std::process::id()
        ));
        let file = OpenOptions::new()
            .read(true)
            .write(true)
            .create_new(true)
            .open(&path)
            .map_err(|e| e.to_string())?;
        Ok(Self { file, path })
    }
}
impl Drop for Scratch {
    fn drop(&mut self) {
        use std::os::unix::fs::MetadataExt;
        if let (Ok(open), Ok(named)) = (self.file.metadata(), std::fs::symlink_metadata(&self.path))
        {
            if open.ino() == named.ino() && open.dev() == named.dev() {
                let _ = std::fs::remove_file(&self.path);
            }
        }
    }
}
fn file_io(config: &Config) -> Result<Vec<(&'static str, &'static str, f64)>, String> {
    let mut scratch = Scratch::new(
        config
            .directory
            .as_ref()
            .ok_or("missing benchmark directory")?,
    )?;
    let mut buffer = vec![0_u8; config.size_mib * 1048576];
    // Deterministic varying data reduces the all-zero/compression shortcut;
    // preparation is excluded from the write timing.
    let mut data = 0x123456789abcdef_u64;
    for word in buffer.chunks_exact_mut(8) {
        data ^= data << 13;
        data ^= data >> 7;
        data ^= data << 17;
        word.copy_from_slice(&data.to_ne_bytes());
    }
    let start = Instant::now();
    scratch.file.write_all(&buffer).map_err(|e| e.to_string())?;
    scratch.file.sync_data().map_err(|e| e.to_string())?;
    let write_seconds = start.elapsed().as_secs_f64();
    scratch
        .file
        .seek(SeekFrom::Start(0))
        .map_err(|e| e.to_string())?;
    let start = Instant::now();
    scratch
        .file
        .read_exact(&mut buffer)
        .map_err(|e| e.to_string())?;
    let read_seconds = start.elapsed().as_secs_f64();
    black_box(&buffer);
    // Report cleanup failures rather than silently leaving a normal completed run's file.
    std::fs::remove_file(&scratch.path)
        .map_err(|e| format!("temporary file cleanup failed: {e}"))?;
    Ok(vec![
        (
            "file write + sync_data",
            "MiB/s",
            config.size_mib as f64 / write_seconds,
        ),
        (
            "file read (page cache allowed)",
            "MiB/s",
            config.size_mib as f64 / read_seconds,
        ),
    ])
}

fn directory_filesystem(directory: &std::path::Path) -> Result<String, String> {
    use std::os::unix::ffi::OsStrExt;
    let path =
        std::ffi::CString::new(directory.as_os_str().as_bytes()).map_err(|e| e.to_string())?;
    let mut data = std::mem::MaybeUninit::<libc::statfs>::uninit();
    // statfs initializes the output structure on success; the CString remains
    // alive through the call and contains exactly the selected directory path.
    let data = unsafe {
        if libc::statfs(path.as_ptr(), data.as_mut_ptr()) != 0 {
            return Err(std::io::Error::last_os_error().to_string());
        }
        data.assume_init()
    };
    let magic = data.f_type as u64;
    let name = match magic {
        0x01021994 => "tmpfs",
        0x794c7630 => "overlay",
        0xef53 => "ext-family",
        0x58465342 => "xfs",
        0x9123683e => "btrfs",
        0x6969 => "nfs",
        _ => "other",
    };
    Ok(format!("{name} (statfs magic 0x{magic:x})"))
}

pub fn execute(kind: Kind, config: Config) -> Result<Report, String> {
    config.validate(kind)?;
    let mut kernel = Kernel::live();
    let before = kernel.sample();
    let mut environment: Vec<(String, String)> = before
        .metrics
        .iter()
        .filter(|m| {
            m.topic == Topic::Summary
                && (m.name.starts_with("CPU")
                    || m.name.starts_with("NUMA")
                    || m.name.starts_with("内存")
                    || m.name.starts_with("容器")
                    || m.name.starts_with("系统")
                    || m.name == "存储 · 根文件系统")
        })
        .take(24)
        .map(|m| (m.name.clone(), m.value.chars().take(256).collect()))
        .collect();
    if kind == Kind::FileIo {
        let directory = config.directory.as_ref().ok_or("missing directory")?;
        environment.push((
            "文件测试 · 实际目录文件系统".into(),
            directory_filesystem(directory).unwrap_or_else(|e| format!("N/A: {e}")),
        ));
    }
    let started_unix_ms = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis();
    let start = Instant::now();
    let mut samples: Vec<Measurement> = Vec::new();
    for _ in 0..config.rounds {
        let duration = Duration::from_millis(config.duration_ms);
        let values = match kind {
            Kind::Cpu => cpu(duration)?,
            Kind::Memory => memory(duration, config.size_mib * 1048576)?,
            Kind::Scheduler => scheduler(duration)?,
            Kind::TcpLoopback => tcp(duration)?,
            Kind::FileIo => file_io(&config)?,
        };
        for (name, unit, value) in values {
            if let Some(measurement) = samples.iter_mut().find(|m| m.name == name) {
                measurement.values.push(value);
            } else {
                samples.push(Measurement {
                    name: name.into(),
                    unit: unit.into(),
                    values: vec![value],
                    median: 0.0,
                    min: 0.0,
                    max: 0.0,
                });
            }
        }
    }
    let measurements = samples
        .into_iter()
        .map(|m| Measurement::new(&m.name, &m.unit, m.values))
        .collect::<Result<_, _>>()?;
    let elapsed_ms = start.elapsed().as_millis();
    let after = kernel.sample();
    let notes = vec![
        kind.explanation().into(),
        "未固定 CPU/NUMA；共享负载、频率变化、虚拟化和祖先 cgroup 可能影响结果。轮次区间是观测 min/max，不是置信区间。".into(),
    ];
    Ok(Report {
        schema_version: 1,
        kind,
        config,
        started_unix_ms,
        elapsed_ms,
        build_mode: if cfg!(debug_assertions) {
            "debug (use release for comparisons)"
        } else {
            "release"
        }
        .into(),
        workload_version: 1,
        environment,
        measurements,
        observations_before: observations(&before),
        observations_after: observations(&after),
        notes,
    })
}

fn reader(pipe: impl Read + Send + 'static) -> JoinHandle<Result<Vec<u8>, String>> {
    std::thread::spawn(move || {
        let mut bytes = Vec::new();
        pipe.take(65537)
            .read_to_end(&mut bytes)
            .map_err(|e| e.to_string())?;
        if bytes.len() > 65536 {
            Err("benchmark output exceeded 64 KiB".into())
        } else {
            Ok(bytes)
        }
    })
}

struct ScratchDirectory {
    path: PathBuf,
    identity: (u64, u64, u32),
    worker_pid: Option<u32>,
    cleaned: bool,
}
impl ScratchDirectory {
    fn new(parent: &std::path::Path) -> Result<Self, String> {
        use std::os::unix::fs::{DirBuilderExt, MetadataExt};
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_nanos();
        let path = parent.join(format!(".kernel-lens-run-{}-{nonce}", std::process::id()));
        std::fs::DirBuilder::new()
            .mode(0o700)
            .create(&path)
            .map_err(|e| e.to_string())?;
        let metadata = std::fs::symlink_metadata(&path).map_err(|e| e.to_string())?;
        Ok(Self {
            path,
            identity: (metadata.dev(), metadata.ino(), metadata.uid()),
            worker_pid: None,
            cleaned: false,
        })
    }
    fn cleanup(&mut self) -> Result<(), String> {
        use std::os::unix::fs::MetadataExt;
        if self.cleaned {
            return Ok(());
        }
        let metadata = std::fs::symlink_metadata(&self.path).map_err(|e| e.to_string())?;
        if !metadata.is_dir() || (metadata.dev(), metadata.ino(), metadata.uid()) != self.identity {
            return Err("scratch directory identity changed; retained".into());
        }
        let entries = std::fs::read_dir(&self.path)
            .map_err(|e| e.to_string())?
            .take(9)
            .collect::<Result<Vec<_>, _>>()
            .map_err(|e| e.to_string())?;
        if entries.len() > 8 {
            return Err("unexpected scratch contents; retained".into());
        }
        let prefix = self
            .worker_pid
            .map(|pid| format!(".kernel-lens-bench-{pid}-"));
        for entry in &entries {
            let name = entry.file_name().to_string_lossy().into_owned();
            let valid_name = prefix
                .as_ref()
                .and_then(|prefix| name.strip_prefix(prefix))
                .is_some_and(|suffix| {
                    !suffix.is_empty() && suffix.bytes().all(|b| b.is_ascii_digit())
                });
            let file = std::fs::symlink_metadata(entry.path()).map_err(|e| e.to_string())?;
            if !valid_name || !file.is_file() || file.nlink() != 1 || file.uid() != self.identity.2
            {
                return Err("unrecognized scratch file; retained".into());
            }
        }
        for entry in entries {
            std::fs::remove_file(entry.path()).map_err(|e| e.to_string())?;
        }
        std::fs::remove_dir(&self.path).map_err(|e| e.to_string())?;
        self.cleaned = true;
        Ok(())
    }
}
impl Drop for ScratchDirectory {
    fn drop(&mut self) {
        let _ = self.cleanup();
    }
}

pub struct Runner {
    child: Option<Child>,
    stdout: Option<JoinHandle<Result<Vec<u8>, String>>>,
    stderr: Option<JoinHandle<Result<Vec<u8>, String>>>,
    started: Instant,
    scratch: Option<ScratchDirectory>,
    requested: Config,
}
impl Runner {
    pub fn start(kind: Kind, config: &Config) -> Result<Self, String> {
        config.validate(kind)?;
        let mut scratch = if kind == Kind::FileIo {
            Some(ScratchDirectory::new(
                config.directory.as_ref().ok_or("missing directory")?,
            )?)
        } else {
            None
        };
        let mut command = Command::new(std::env::current_exe().map_err(|e| e.to_string())?);
        command.args([
            "--bench-worker",
            kind.id(),
            "--bench-duration-ms",
            &config.duration_ms.to_string(),
            "--bench-rounds",
            &config.rounds.to_string(),
            "--bench-size-mib",
            &config.size_mib.to_string(),
        ]);
        if let Some(directory) = scratch
            .as_ref()
            .map(|s| &s.path)
            .or(config.directory.as_ref())
        {
            command.arg("--bench-dir").arg(directory);
        }
        // The worker has no subprocesses. Stop this exact owned worker if its
        // parent exits abruptly; the post-prctl parent check closes the fork race.
        #[cfg(target_os = "linux")]
        unsafe {
            use std::os::unix::process::CommandExt;
            let parent = libc::getpid();
            command.pre_exec(move || {
                if libc::prctl(libc::PR_SET_PDEATHSIG, libc::SIGKILL) != 0 {
                    return Err(std::io::Error::last_os_error());
                }
                if libc::getppid() != parent {
                    return Err(std::io::Error::other("benchmark parent exited"));
                }
                Ok(())
            });
        }
        let mut child = command
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| e.to_string())?;
        if let Some(scratch) = &mut scratch {
            scratch.worker_pid = Some(child.id());
        }
        let stdout = Some(reader(child.stdout.take().ok_or("missing worker stdout")?));
        let stderr = Some(reader(child.stderr.take().ok_or("missing worker stderr")?));
        Ok(Self {
            child: Some(child),
            stdout,
            stderr,
            started: Instant::now(),
            scratch,
            requested: config.clone(),
        })
    }
    pub fn poll(&mut self) -> Option<Result<Report, String>> {
        if self.started.elapsed() > Duration::from_secs(30) {
            let cleanup = self.stop();
            return Some(Err(format!(
                "benchmark exceeded 30 s; worker terminated{}",
                cleanup
                    .err()
                    .map(|e| format!("; cleanup: {e}"))
                    .unwrap_or_default()
            )));
        }
        let status = match self.child.as_mut()?.try_wait() {
            Ok(None) => return None,
            Ok(Some(status)) => status,
            Err(e) => {
                let cleanup = self.stop();
                return Some(Err(format!("{e}; cleanup={cleanup:?}")));
            }
        };
        self.child.take();
        let stdout = self
            .stdout
            .take()?
            .join()
            .unwrap_or_else(|_| Err("stdout reader panicked".into()));
        let stderr = self
            .stderr
            .take()?
            .join()
            .unwrap_or_else(|_| Err("stderr reader panicked".into()));
        let cleanup = self.cleanup();
        Some((|| {
            let stdout = stdout?;
            let stderr = stderr?;
            cleanup?;
            if !status.success() {
                let error = String::from_utf8_lossy(&stderr)
                    .trim()
                    .chars()
                    .take(2048)
                    .collect::<String>();
                return Err(if error.is_empty() {
                    format!("benchmark worker exited {status}")
                } else {
                    error
                });
            }
            let mut report: Report = serde_json::from_slice(&stdout).map_err(|e| e.to_string())?;
            report.config = self.requested.clone();
            Ok(report)
        })())
    }
    fn cleanup(&mut self) -> Result<(), String> {
        if let Some(scratch) = &mut self.scratch {
            scratch.cleanup()?;
        }
        self.scratch = None;
        Ok(())
    }
    pub fn stop(&mut self) -> Result<(), String> {
        if let Some(mut child) = self.child.take() {
            let _ = child.kill();
            child.wait().map_err(|e| e.to_string())?;
        }
        if let Some(reader) = self.stdout.take() {
            let _ = reader.join();
        }
        if let Some(reader) = self.stderr.take() {
            let _ = reader.join();
        }
        self.cleanup()
    }
}
impl Drop for Runner {
    fn drop(&mut self) {
        let _ = self.stop();
    }
}

pub struct Session {
    pub config: Config,
    pub selected: [bool; 5],
    pub cursor: usize,
    pub detail: bool,
    pub result_scroll: u16,
    pub results: Vec<(Kind, Result<Report, String>)>,
    pub message: String,
    pub active: Option<Kind>,
    pending: VecDeque<Kind>,
    runner: Option<Runner>,
}
impl Session {
    pub fn new(config: Config) -> Self {
        Self {
            config,
            selected: [false; 5],
            cursor: 0,
            detail: false,
            result_scroll: 0,
            results: Vec::new(),
            message: "Space 勾选项目，r 运行；默认没有自动测试".into(),
            active: None,
            pending: VecDeque::new(),
            runner: None,
        }
    }
    pub fn start_selected(&mut self) {
        if self.active.is_some() {
            self.message = "已有测试运行；c 可取消当前批次".into();
            return;
        }
        self.pending = Kind::ALL
            .into_iter()
            .enumerate()
            .filter(|(i, _)| self.selected[*i])
            .map(|(_, kind)| kind)
            .collect();
        if self.pending.is_empty() {
            self.message = "先用 Space 勾选测试项目".into();
            return;
        }
        self.results.clear();
        self.result_scroll = 0;
        self.message = "按选择顺序运行；c 取消".into();
        self.poll();
    }
    pub fn poll(&mut self) {
        if let Some(runner) = &mut self.runner {
            if let Some(result) = runner.poll() {
                if let Some(kind) = self.active.take() {
                    self.results.push((kind, result));
                }
                self.runner = None;
            }
        }
        while self.runner.is_none() {
            let Some(kind) = self.pending.pop_front() else {
                break;
            };
            match Runner::start(kind, &self.config) {
                Ok(runner) => {
                    self.active = Some(kind);
                    self.runner = Some(runner);
                }
                Err(error) => self.results.push((kind, Err(error))),
            }
        }
    }
    pub fn cancel(&mut self) {
        self.pending.clear();
        if let Some(mut runner) = self.runner.take() {
            if let Err(error) = runner.stop() {
                self.message = format!("取消后清理失败: {error}");
                if let Some(kind) = self.active.take() {
                    self.results.push((kind, Err(self.message.clone())));
                }
                return;
            }
        }
        if let Some(kind) = self.active.take() {
            self.results.push((
                kind,
                Err("cancelled; owned worker stopped and temporary files cleaned".into()),
            ));
        }
        self.message = "已取消当前批次".into();
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn statistics_keep_rounds_and_use_midpoint_for_even_counts() {
        let m = Measurement::new("x", "unit", vec![5.0, 1.0, 3.0, 7.0]).unwrap();
        assert_eq!(m.values, vec![5.0, 1.0, 3.0, 7.0]);
        assert_eq!(m.median, 4.0);
        assert_eq!((m.min, m.max), (1.0, 7.0));
        assert!(Measurement::new("x", "u", vec![f64::NAN]).is_err());
    }
    #[test]
    fn disk_requires_explicit_existing_directory_and_work_is_bounded() {
        assert!(Config::default().validate(Kind::FileIo).is_err());
        assert!(Config {
            duration_ms: 0,
            ..Config::default()
        }
        .validate(Kind::Cpu)
        .is_err());
        assert!(Config {
            size_mib: 65,
            ..Config::default()
        }
        .validate(Kind::Memory)
        .is_err());
        assert!(Config {
            rounds: 8,
            ..Config::default()
        }
        .validate(Kind::Cpu)
        .is_err());
    }
    #[test]
    fn no_selection_does_not_start_any_worker() {
        let mut session = Session::new(Config::default());
        session.start_selected();
        session.poll();
        assert!(session.active.is_none());
        assert!(session.results.is_empty());
        assert!(session.runner.is_none());
    }
    #[test]
    fn scratch_cleanup_retains_unknown_files() {
        let mut scratch = ScratchDirectory::new(&std::env::temp_dir()).unwrap();
        let unknown = scratch.path.join("unrecognized");
        std::fs::write(&unknown, "keep").unwrap();
        assert!(scratch.cleanup().is_err());
        assert_eq!(std::fs::read_to_string(&unknown).unwrap(), "keep");
        std::fs::remove_file(unknown).unwrap();
        scratch.cleanup().unwrap();
    }
}
