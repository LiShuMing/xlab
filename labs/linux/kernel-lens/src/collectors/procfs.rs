use super::{key_values, Collector, LinuxFs};
use crate::model::{Metric, Rates, State, Topic};
use std::collections::HashMap;
use std::time::Instant;

#[derive(Default)]
pub struct ProcCollector {
    rates: Rates,
    cpus: HashMap<String, (u64, u64)>,
}

// guest and guest_nice are already included in user/nice; do not count them twice.
pub fn cpu_ticks(fields: &str) -> Option<(u64, u64)> {
    let values: Vec<u64> = fields
        .split_whitespace()
        .take(8)
        .map(str::parse)
        .collect::<Result<_, _>>()
        .ok()?;
    if values.len() < 4 {
        return None;
    }
    let total = values
        .iter()
        .try_fold(0_u64, |sum, n| sum.checked_add(*n))?;
    let idle = values[3].checked_add(*values.get(4).unwrap_or(&0))?;
    Some((total, idle))
}

pub fn cpu_busy(before: (u64, u64), after: (u64, u64)) -> Option<f64> {
    let total = after.0.checked_sub(before.0)?;
    let idle = after.1.checked_sub(before.1)?;
    if total == 0 || idle > total {
        return None;
    }
    Some(100.0 * (total - idle) as f64 / total as f64)
}

fn rate_metric(
    topic: Topic,
    name: String,
    rate: Option<f64>,
    unit: &str,
    scope: &str,
    source: &str,
    explanation: &str,
) -> Metric {
    let mut metric = Metric::new(
        topic,
        name,
        rate.map(|v| format!("{v:.1}"))
            .unwrap_or_else(|| "warming/reset".into()),
        unit,
        scope,
        source,
        explanation,
    );
    if rate.is_none() {
        metric.state = State::Warming;
    }
    metric
}

impl Collector for ProcCollector {
    fn collect(&mut self, fs: &LinuxFs, now: Instant) -> Vec<Metric> {
        let mut out = Vec::new();
        for (path, name) in [
            ("/proc/sys/kernel/osrelease", "kernel"),
            ("/proc/sys/kernel/hostname", "hostname"),
            ("/proc/uptime", "uptime / idle seconds"),
        ] {
            match fs.read(path) {
                Ok(text) => out.push(Metric::new(Topic::Overview, name, text.trim(), "", "visible kernel", path,
                    "容器共享内核；hostname 属于当前 UTS namespace。uptime 的 idle 可累计多个 CPU。")),
                Err(e) => out.push(Metric::unavailable(Topic::Overview, name, path, e)),
            }
        }
        for namespace in ["pid", "net", "mnt", "uts", "user", "cgroup"] {
            let path = format!("/proc/self/ns/{namespace}");
            match fs.link(&path) {
                Ok(link) => out.push(Metric::new(
                    Topic::Overview,
                    format!("namespace {namespace}"),
                    link.to_string_lossy(),
                    "",
                    "current process",
                    &path,
                    "标识当前进程所在 namespace；仅凭这个编号不能判断是否与宿主机相同。",
                )),
                Err(e) => out.push(Metric::unavailable(Topic::Overview, namespace, &path, e)),
            }
        }
        match fs.read("/proc/self/status") {
            Ok(text) => {
                for (key, value) in key_values(&text) {
                    if [
                        "Cpus_allowed_list",
                        "Mems_allowed_list",
                        "Seccomp",
                        "CapEff",
                    ]
                    .contains(&key)
                    {
                        out.push(Metric::new(Topic::Overview, key, value, "", "current process",
                        "/proc/self/status", "进程的 CPU/内存节点许可、seccomp 过滤模式和有效 capability 位图；不代表所有权限检查都已通过。"));
                    }
                }
            }
            Err(e) => out.push(Metric::unavailable(
                Topic::Overview,
                "process status",
                "/proc/self/status",
                e,
            )),
        }
        match fs.read("/proc/loadavg") {
            Ok(text) => out.push(Metric::new(
                Topic::Cpu,
                "load 1/5/15m, runnable/total, last PID",
                text.trim(),
                "",
                "proc view; not cgroup-local",
                "/proc/loadavg",
                "load 包含运行队列与不可中断睡眠任务；可能看到宿主机或虚拟化后的值。",
            )),
            Err(e) => out.push(Metric::unavailable(Topic::Cpu, "load", "/proc/loadavg", e)),
        }
        match fs.read("/proc/stat") {
            Ok(text) => {
                let mut seen = Vec::new();
                for (key, value) in key_values(&text) {
                    if key == "cpu"
                        || key
                            .strip_prefix("cpu")
                            .is_some_and(|s| !s.is_empty() && s.bytes().all(|b| b.is_ascii_digit()))
                    {
                        if let Some(current) = cpu_ticks(value) {
                            let busy = self
                                .cpus
                                .insert(key.into(), current)
                                .and_then(|old| cpu_busy(old, current));
                            out.push(rate_metric(Topic::Cpu, format!("{key} busy"), busy, "%", "proc view; not cgroup-local",
                                "/proc/stat", "(总 tick 差分 - idle/iowait 差分) / 总 tick 差分。guest 不重复计入；iowait 不等于设备忙碌率。"));
                            seen.push(key.to_owned());
                        } else {
                            out.push(Metric::unavailable(
                                Topic::Cpu,
                                key,
                                "/proc/stat",
                                "malformed CPU counters",
                            ));
                        }
                    } else if ["ctxt", "processes"].contains(&key) {
                        if let Ok(count) = value.parse() {
                            out.push(rate_metric(
                                Topic::Cpu,
                                format!("{key}/s"),
                                self.rates.sample(key, count, now),
                                "events/s",
                                "proc view; not cgroup-local",
                                "/proc/stat",
                                "上下文切换/新建任务累计次数的差分；无法由此推出调度延迟。",
                            ));
                        }
                    } else if ["procs_running", "procs_blocked"].contains(&key) {
                        out.push(Metric::new(Topic::Cpu, key, value, "tasks", "proc view; not cgroup-local", "/proc/stat",
                            "采样时刻的可运行或阻塞任务数量；属于可见系统统计，不是当前容器独立队列。"));
                    }
                }
                self.cpus.retain(|key, _| seen.contains(key));
            }
            Err(e) => {
                self.cpus.clear();
                out.push(Metric::unavailable(
                    Topic::Cpu,
                    "CPU counters",
                    "/proc/stat",
                    e,
                ));
            }
        }
        match fs.read("/proc/meminfo") {
            Ok(text) => {
                for (key, value) in key_values(&text) {
                    if [
                        "MemTotal",
                        "MemFree",
                        "MemAvailable",
                        "Cached",
                        "SwapTotal",
                        "SwapFree",
                        "Dirty",
                        "Writeback",
                        "AnonHugePages",
                    ]
                    .contains(&key)
                    {
                        out.push(Metric::new(Topic::Memory, key, value, "", "proc view; not cgroup-local", "/proc/meminfo",
                        "可见系统内存统计。容器用量/上限请看 cgroup 行；MemAvailable 包含可回收内存的估计。"));
                    }
                }
            }
            Err(e) => out.push(Metric::unavailable(
                Topic::Memory,
                "memory",
                "/proc/meminfo",
                e,
            )),
        }
        for (resource, topic) in [
            ("cpu", Topic::Cpu),
            ("memory", Topic::Memory),
            ("io", Topic::Storage),
        ] {
            let path = format!("/proc/pressure/{resource}");
            match fs.read(&path) {
                Ok(text) => {
                    for line in text.lines() {
                        out.push(Metric::new(topic, format!("PSI {resource}"), line, "", "proc view; not cgroup-local", &path,
                        "PSI：some=至少一个任务受阻，full=所有非空闲任务受阻；avg10/60/300 是百分比，total 是累计微秒。"));
                    }
                }
                Err(e) => out.push(Metric::unavailable(
                    topic,
                    &format!("PSI {resource}"),
                    &path,
                    e,
                )),
            }
        }
        match fs.read("/proc/net/dev") {
            Ok(text) => {
                for line in text.lines().skip(2) {
                    if let Some((interface, fields)) = line.split_once(':') {
                        let name = interface.trim();
                        let values: Vec<_> = fields.split_whitespace().collect();
                        if values.len() < 16 {
                            out.push(Metric::unavailable(
                                Topic::Network,
                                name,
                                "/proc/net/dev",
                                "malformed interface counters",
                            ));
                            continue;
                        }
                        for (direction, index) in [("RX", 0), ("TX", 8)] {
                            if let Ok(bytes) = values[index].parse() {
                                out.push(rate_metric(Topic::Network, format!("{name} {direction}"),
                                self.rates.sample(&format!("net:{name}:{direction}"), bytes, now), "B/s", "current net namespace", "/proc/net/dev",
                                "接口字节累计值差分。虚拟网卡/回环也在此列出；不包含 RTT 或重传归因。"));
                            }
                        }
                        out.push(Metric::new(
                            Topic::Network,
                            format!("{name} errors / drops RX TX"),
                            format!(
                                "{} / {}   {} / {}",
                                values[2], values[3], values[10], values[11]
                            ),
                            "total",
                            "current net namespace",
                            "/proc/net/dev",
                            "接口累计错误和丢包；这些计数不是 TCP 重传，也不直接证明链路故障。",
                        ));
                    }
                }
            }
            Err(e) => out.push(Metric::unavailable(
                Topic::Network,
                "interfaces",
                "/proc/net/dev",
                e,
            )),
        }
        match fs.read("/proc/net/sockstat") {
            Ok(text) => {
                for line in text.lines() {
                    out.push(Metric::new(
                        Topic::Network,
                        "socket summary",
                        line,
                        "",
                        "current net namespace (some memory fields kernel-wide)",
                        "/proc/net/sockstat",
                        "TCP inuse/orphan/tw 等 socket 汇总；部分内存统计可能是全内核口径。",
                    ));
                }
            }
            Err(e) => out.push(Metric::unavailable(
                Topic::Network,
                "sockets",
                "/proc/net/sockstat",
                e,
            )),
        }
        match fs.read("/proc/diskstats") {
            Ok(text) => {
                for line in text.lines() {
                    let fields: Vec<_> = line.split_whitespace().collect();
                    if fields.len() < 14 {
                        continue;
                    }
                    let name = fields[2];
                    for (label, index, factor, unit) in [
                        ("read", 5, 512.0, "B/s"),
                        ("write", 9, 512.0, "B/s"),
                        ("read IOPS", 3, 1.0, "ops/s"),
                        ("write IOPS", 7, 1.0, "ops/s"),
                    ] {
                        if let Ok(count) = fields[index].parse() {
                            let rate = self
                                .rates
                                .sample(&format!("disk:{name}:{label}"), count, now)
                                .map(|v| v * factor);
                            out.push(rate_metric(Topic::Storage, format!("{name} {label}"), rate, unit,
                            "visible block devices; not cgroup-local", "/proc/diskstats",
                            "块层计数差分。含分区和设备映射层，不可简单求和；字节统计的扇区大小固定为 512 B。"));
                        }
                    }
                    out.push(Metric::new(
                        Topic::Storage,
                        format!("{name} in-flight"),
                        fields[11],
                        "requests",
                        "visible block devices; not cgroup-local",
                        "/proc/diskstats",
                        "当前进行中的块请求数量，不是文件系统用量，也不是设备队列上限。",
                    ));
                }
            }
            Err(e) => out.push(Metric::unavailable(
                Topic::Storage,
                "block devices",
                "/proc/diskstats",
                e,
            )),
        }
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn guest_ticks_are_not_counted_twice() {
        assert_eq!(cpu_ticks("10 20 30 40 5 6 7 8 100 200"), Some((126, 45)));
        assert_eq!(cpu_ticks("broken"), None);
        assert_eq!(cpu_busy((100, 50), (200, 70)), Some(80.0));
        assert_eq!(cpu_busy((100, 50), (50, 20)), None);
        assert_eq!(cpu_busy((100, 50), (101, 60)), None);
    }
}
