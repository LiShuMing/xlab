use kernel_lens::collectors::{Kernel, LinuxFs};
use kernel_lens::model::{State, Topic};
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};

static NEXT: AtomicU64 = AtomicU64::new(0);
struct Fixture(PathBuf);
impl Fixture {
    fn new() -> Self {
        let path = std::env::temp_dir().join(format!(
            "kernel-lens-{}-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        std::fs::create_dir(&path).unwrap();
        Self(path)
    }
    fn write(&self, path: &str, content: &str) {
        let full = self.0.join(path.trim_start_matches('/'));
        std::fs::create_dir_all(full.parent().unwrap()).unwrap();
        std::fs::write(full, content).unwrap();
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        std::fs::remove_dir_all(&self.0).unwrap();
    }
}

#[test]
fn missing_sources_are_explicit_and_snapshot_is_serializable() {
    let fixture = Fixture::new();
    let mut kernel = Kernel::new(LinuxFs::new(&fixture.0));
    let snapshot = kernel.sample();
    for topic in Topic::ALL
        .into_iter()
        .filter(|topic| *topic != Topic::Benchmark)
    {
        assert!(snapshot
            .metrics
            .iter()
            .any(|m| m.topic == topic && matches!(m.state, State::Unavailable)));
    }
    assert!(snapshot
        .metrics
        .iter()
        .filter(|m| m.source.starts_with("/proc/") || m.source.starts_with("/sys/"))
        .all(|m| matches!(m.state, State::Unavailable)));
    let json = serde_json::to_value(&snapshot).unwrap();
    assert_eq!(json["schema_version"], 1);
    assert_eq!(json["sequence"], 1);
    assert_eq!(kernel.sample().sequence, 2);
}

#[test]
fn reads_current_v2_group_not_mount_root() {
    let fixture = Fixture::new();
    fixture.write("/proc/self/cgroup", "0::/tenant/app\n");
    fixture.write(
        "/proc/self/mountinfo",
        "31 20 0:27 /tenant /visible rw - cgroup2 cgroup rw\n",
    );
    fixture.write("/visible/memory.max", "WRONG_ROOT\n");
    fixture.write("/visible/app/memory.max", "max\n");
    fixture.write("/visible/app/cpu.max", "150000 100000\n");
    fixture.write("/visible/app/cpu.stat", "usage_usec 100\nnr_throttled 3\n");
    let snapshot = Kernel::new(LinuxFs::new(&fixture.0)).sample();
    let memory = snapshot
        .metrics
        .iter()
        .find(|m| m.name == "memory.max")
        .unwrap();
    assert_eq!(memory.value, "max");
    assert_eq!(memory.source, "/visible/app/memory.max");
    assert!(snapshot
        .metrics
        .iter()
        .any(|m| m.name == "cpu.stat" && m.value == "nr_throttled 3"));
}

#[test]
fn reads_v1_memory_and_reports_other_missing_controllers() {
    let fixture = Fixture::new();
    fixture.write("/proc/self/cgroup", "2:memory:/job\n3:cpu,cpuacct:/job\n");
    fixture.write("/proc/self/mountinfo", "31 20 0:27 / /cg/memory rw - cgroup cgroup rw,memory\n32 20 0:28 / /cg/cpu rw - cgroup cgroup rw,cpu,cpuacct\n");
    fixture.write("/cg/memory/job/memory.usage_in_bytes", "1024\n");
    let snapshot = Kernel::new(LinuxFs::new(&fixture.0)).sample();
    assert!(snapshot
        .metrics
        .iter()
        .any(|m| m.name == "memory.usage_in_bytes" && m.value == "1024"));
    assert!(snapshot
        .metrics
        .iter()
        .any(|m| m.name == "cpu.cfs_quota_us" && matches!(m.state, State::Unavailable)));
}

#[test]
fn filesystem_reads_are_bounded() {
    let fixture = Fixture::new();
    fixture.write("/too-large", &"x".repeat(4 * 1024 * 1024 + 1));
    assert_eq!(
        LinuxFs::new(&fixture.0)
            .read("/too-large")
            .unwrap_err()
            .kind(),
        std::io::ErrorKind::InvalidData
    );
}

#[test]
fn overview_keeps_host_memory_and_container_limit_separate() {
    let fixture = Fixture::new();
    fixture.write(
        "/proc/meminfo",
        "MemTotal: 10485760 kB\nMemAvailable: 2097152 kB\n",
    );
    fixture.write("/proc/self/cgroup", "0::/app\n");
    fixture.write(
        "/proc/self/mountinfo",
        "31 20 0:27 / /cg rw - cgroup2 cgroup rw\n",
    );
    fixture.write("/cg/app/memory.max", "1073741824\n");
    let snapshot = Kernel::new(LinuxFs::new(&fixture.0)).sample();
    let system = snapshot
        .metrics
        .iter()
        .find(|m| m.topic == Topic::Summary && m.name == "内存 · MemTotal")
        .unwrap();
    let limit = snapshot
        .metrics
        .iter()
        .find(|m| m.topic == Topic::Summary && m.name == "容器 · 内存上限 bytes")
        .unwrap();
    assert_eq!(system.value, "10.00 GiB");
    assert_eq!(limit.value, "1073741824");
    assert_ne!(system.scope, limit.scope);
    assert_eq!(limit.source, "/cg/app/memory.max");
}
