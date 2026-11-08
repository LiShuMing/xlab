use super::{Collector, LinuxFs};
use crate::model::{Metric, Topic};
use std::path::Path;
use std::time::Instant;

pub struct SysCollector;
pub struct CapabilityCollector;

impl Collector for SysCollector {
    fn collect(&mut self, fs: &LinuxFs, _now: Instant) -> Vec<Metric> {
        let mut out = Vec::new();
        for (path, topic, name, explanation) in [
            (
                "/sys/devices/system/cpu/online",
                Topic::Cpu,
                "online CPUs",
                "系统 online CPU 集合；当前进程获准使用的集合见环境页 Cpus_allowed_list。",
            ),
            (
                "/sys/devices/system/cpu/smt/active",
                Topic::Cpu,
                "SMT active",
                "同时多线程：1 为启用；逻辑 CPU 不等于独立物理核心。",
            ),
            (
                "/sys/devices/system/node/online",
                Topic::Numa,
                "online nodes",
                "可见 NUMA 节点；cpuset 和进程内存策略可以限制实际使用范围。",
            ),
            (
                "/proc/sys/kernel/numa_balancing",
                Topic::Numa,
                "automatic NUMA balancing",
                "1 表示内核自动 NUMA 平衡启用；这是开关值，不是迁移是否发生的证据。",
            ),
            (
                "/sys/kernel/mm/transparent_hugepage/enabled",
                Topic::Memory,
                "transparent huge pages",
                "透明大页策略；方括号中为当前模式。大页可能减少 TLB 缺失，也可能增加整理开销。",
            ),
        ] {
            match fs.read(path) {
                Ok(text) => out.push(Metric::new(
                    topic,
                    name,
                    text.trim(),
                    "",
                    "visible sys/kernel",
                    path,
                    explanation,
                )),
                Err(e) => out.push(Metric::unavailable(topic, name, path, e)),
            }
        }
        let root = "/sys/devices/system/node";
        match std::fs::read_dir(fs.path(root)) {
            Ok(entries) => {
                let mut nodes: Vec<_> = entries
                    .filter_map(Result::ok)
                    .filter_map(|e| e.file_name().into_string().ok())
                    .filter(|name| {
                        name.strip_prefix("node")
                            .is_some_and(|n| !n.is_empty() && n.bytes().all(|b| b.is_ascii_digit()))
                    })
                    .take(4096)
                    .collect();
                nodes.sort();
                for node in nodes {
                    for file in ["cpulist", "distance", "numastat", "meminfo"] {
                        let path = format!("{root}/{node}/{file}");
                        match fs.read(&path) {
                            Ok(text) => {
                                for line in text.lines().filter(|line| {
                                    file != "meminfo"
                                        || line.contains("MemTotal")
                                        || line.contains("MemFree")
                                }) {
                                    out.push(Metric::new(Topic::Numa, format!("{node} {file}"), line, "", "visible NUMA node; not cgroup-local", &path,
                                    "distance 是节点距离矩阵；numa_hit/miss/foreign 是分配计数，不是 CPU 远程 load 延迟。meminfo 单位 kB。"));
                                }
                            }
                            Err(e) => out.push(Metric::unavailable(
                                Topic::Numa,
                                &format!("{node} {file}"),
                                &path,
                                e,
                            )),
                        }
                    }
                }
            }
            Err(e) => out.push(Metric::unavailable(Topic::Numa, "NUMA topology", root, e)),
        }
        out
    }
}

fn executable_on_path(program: &str) -> Option<String> {
    use std::os::unix::fs::PermissionsExt;
    std::env::var_os("PATH").and_then(|paths| {
        std::env::split_paths(&paths).find_map(|dir| {
            let path = dir.join(program);
            let metadata = path.metadata().ok()?;
            (metadata.is_file() && metadata.permissions().mode() & 0o111 != 0)
                .then(|| path.to_string_lossy().into_owned())
        })
    })
}

impl Collector for CapabilityCollector {
    fn collect(&mut self, fs: &LinuxFs, _now: Instant) -> Vec<Metric> {
        let mut out = Vec::new();
        for (path, name, explanation) in [
            ("/proc/sys/kernel/perf_event_paranoid", "perf_event_paranoid", "控制非特权 perf 访问范围，发行版可能扩展含义；capability、seccomp 和 LSM 仍可拒绝调用。"),
            ("/proc/sys/kernel/kptr_restrict", "kptr_restrict", "限制内核符号地址可见性，影响符号解析。"),
            ("/proc/sys/kernel/unprivileged_bpf_disabled", "unprivileged_bpf_disabled", "非特权 BPF 开关：0 允许，1 禁止且通常不可回退，2 禁止但管理员可回退；仍需实际加载验证。"),
            ("/sys/kernel/security/lockdown", "kernel lockdown", "内核 lockdown 策略可能限制 perf/BPF；读取失败不代表策略关闭。"),
        ] {
            match fs.read(path) {
                Ok(text) => out.push(Metric::new(Topic::Capabilities, name, text.trim(), "", "visible kernel policy", path, explanation)),
                Err(e) => out.push(Metric::unavailable(Topic::Capabilities, name, path, e)),
            }
        }
        for (path, name) in [
            ("/sys/kernel/btf/vmlinux", "BTF type metadata"),
            ("/sys/kernel/tracing/events", "tracefs events"),
            ("/sys/kernel/debug/tracing/events", "debugfs trace events"),
        ] {
            let metric = match std::fs::metadata(fs.path(path)) {
                Ok(_) => Metric::new(Topic::Capabilities, name, "visible (access unverified)", "", "current mount namespace", path,
                    "仅探测文件存在。BTF 为类型元数据；tracefs 提供事件描述。存在不证明可读、可 attach 或内核支持所有 BPF 类型。"),
                Err(e) => Metric::unavailable(Topic::Capabilities, name, path, e),
            };
            out.push(metric);
        }
        for tool in [
            "perf", "bpftool", "bpftrace", "lscpu", "numactl", "numastat", "vmstat", "pidstat",
            "ip", "ss", "nstat", "iostat", "lsblk", "findmnt",
        ] {
            match executable_on_path(tool) {
                Some(path) => out.push(Metric::new(Topic::Capabilities, tool, "on PATH; not executed", "", "current process PATH", path,
                    "找到可执行文件不等于运行成功或具有权限。学习命令由用户在另一个终端运行；程序不会提权或安装工具。")),
                None => out.push(Metric::unavailable(Topic::Capabilities, tool, "PATH", "executable not found on PATH")),
            }
        }
        out.push(Metric::new(Topic::Capabilities, "BPF event collector", "planned / not loaded", "", "kernel-lens", Path::new("src/collectors").display().to_string(),
            "当前只有轮询观测，没有加载 BPF 程序。后续通过 Collector 接入聚合事件，并显式报告丢失事件、权限、过滤范围和采样窗口。"));
        out
    }
}
