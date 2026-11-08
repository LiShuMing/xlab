use super::{key_values, Collector, LinuxFs};
use crate::model::{Metric, Topic};
use std::collections::BTreeSet;
use std::time::Instant;

pub struct InventoryCollector;

pub fn cpu_list_count(text: &str) -> Option<usize> {
    let mut ids = BTreeSet::new();
    for item in text.trim().split(',') {
        let (first, last) = if let Some((a, b)) = item.split_once('-') {
            (a.parse::<u32>().ok()?, b.parse::<u32>().ok()?)
        } else {
            let n = item.parse::<u32>().ok()?;
            (n, n)
        };
        if first > last || last > 1_000_000 {
            return None;
        }
        ids.extend(first..=last);
    }
    Some(ids.len())
}

pub fn cpu_topology(text: &str) -> (usize, usize, usize) {
    let mut logical = 0;
    let mut sockets = BTreeSet::new();
    let mut cores = BTreeSet::new();
    for record in text.split("\n\n") {
        let fields: std::collections::HashMap<_, _> = record
            .lines()
            .filter_map(|line| line.split_once(':'))
            .map(|(k, v)| (k.trim(), v.trim()))
            .collect();
        if fields.contains_key("processor") {
            logical += 1;
        }
        if let Some(socket) = fields.get("physical id") {
            sockets.insert(*socket);
            if let Some(core) = fields.get("core id") {
                cores.insert((*socket, *core));
            }
        }
    }
    (logical, sockets.len(), cores.len())
}

fn row(
    out: &mut Vec<Metric>,
    name: &str,
    value: impl Into<String>,
    scope: &str,
    source: &str,
    why: &str,
) {
    out.push(Metric::new(
        Topic::Summary,
        name,
        value,
        "",
        scope,
        source,
        why,
    ));
}

fn file_row(fs: &LinuxFs, out: &mut Vec<Metric>, path: &str, name: &str, scope: &str, why: &str) {
    match fs.read(path) {
        Ok(text) => row(out, name, text.trim(), scope, path, why),
        Err(e) => out.push(Metric::unavailable(Topic::Summary, name, path, e)),
    }
}

fn entries(fs: &LinuxFs, root: &str, limit: usize) -> std::io::Result<Vec<String>> {
    let mut names = std::fs::read_dir(fs.path(root))?
        .take(limit)
        .filter_map(Result::ok)
        .filter_map(|entry| entry.file_name().into_string().ok())
        .collect::<Vec<_>>();
    names.sort();
    Ok(names)
}

impl Collector for InventoryCollector {
    fn collect(&mut self, fs: &LinuxFs, _now: Instant) -> Vec<Metric> {
        let mut out = Vec::new();
        row(
            &mut out,
            "系统 · 架构",
            std::env::consts::ARCH,
            "monitor executable target",
            "Rust target architecture",
            "监控程序的目标架构；兼容模式或模拟器下可能与硬件不同。",
        );
        match fs.read("/etc/os-release") {
            Ok(text) => {
                let name = text
                    .lines()
                    .find_map(|line| line.strip_prefix("PRETTY_NAME="))
                    .unwrap_or("unknown");
                row(
                    &mut out,
                    "系统 · 发行版",
                    name.trim_matches('"'),
                    "current filesystem",
                    "/etc/os-release",
                    "当前根文件系统的发行版；容器镜像发行版和宿主机内核可以不同。",
                );
            }
            Err(e) => out.push(Metric::unavailable(
                Topic::Summary,
                "系统 · 发行版",
                "/etc/os-release",
                e,
            )),
        }
        file_row(
            fs,
            &mut out,
            "/proc/sys/kernel/osrelease",
            "系统 · 内核",
            "visible kernel",
            "容器共享所见内核，发行版信息来自当前根文件系统。",
        );
        match fs.read("/proc/cpuinfo") {
            Ok(text) => {
                let model = text
                    .lines()
                    .filter_map(|line| line.split_once(':'))
                    .find(|(k, _)| ["model name", "Hardware", "Processor"].contains(&k.trim()))
                    .map(|(_, v)| v.trim());
                if let Some(model) = model {
                    row(
                        &mut out,
                        "CPU · 型号",
                        model,
                        "proc visible topology",
                        "/proc/cpuinfo",
                        "内核暴露的型号，虚拟机中可能是虚拟 CPU 型号。",
                    );
                }
                let (logical, sockets, cores) = cpu_topology(&text);
                row(&mut out, "CPU · 可见拓扑", format!("{logical} logical CPUs / {} sockets / {} physical cores", if sockets==0 {"unknown".into()} else {sockets.to_string()}, if cores==0 {"unknown".into()} else {cores.to_string()}), "proc visible topology", "/proc/cpuinfo", "按 processor、physical id、core id 去重；unknown sockets/cores 表示该字段未暴露，不能理解成没有硬件。");
            }
            Err(e) => out.push(Metric::unavailable(
                Topic::Summary,
                "CPU · 型号/拓扑",
                "/proc/cpuinfo",
                e,
            )),
        }
        match fs.read("/proc/self/status") {
            Ok(text) => {
                for (key, value) in key_values(&text) {
                    if key == "Cpus_allowed_list" {
                        let count = cpu_list_count(value)
                            .map(|n| n.to_string())
                            .unwrap_or_else(|| "unknown".into());
                        row(&mut out, "CPU · 当前进程许可", format!("{count} logical CPUs [{value}]"), "current process affinity", "/proc/self/status", "这是调度许可集合；CPU 时间配额见容器行，两者都会影响测试。未固定 CPU，测试线程可能迁移。");
                    } else if key == "Mems_allowed_list" {
                        row(
                            &mut out,
                            "NUMA · 当前进程许可",
                            value,
                            "current process",
                            "/proc/self/status",
                            "NUMA 内存节点许可列表；不代表每个节点已有分配。",
                        );
                    }
                }
            }
            Err(e) => out.push(Metric::unavailable(
                Topic::Summary,
                "CPU/NUMA · 进程许可",
                "/proc/self/status",
                e,
            )),
        }
        for (file, label) in [
            ("scaling_governor", "CPU · cpu0 governor"),
            ("scaling_cur_freq", "CPU · cpu0 当前频率 kHz"),
            ("cpuinfo_max_freq", "CPU · cpu0 标称上限 kHz"),
        ] {
            file_row(
                fs,
                &mut out,
                &format!("/sys/devices/system/cpu/cpu0/cpufreq/{file}"),
                label,
                "visible cpu0 policy",
                "仅 cpu0 的可见策略/频率；可能不暴露，当前频率是瞬时值，不能代表整个测试窗口。",
            );
        }
        let cache_root = "/sys/devices/system/cpu/cpu0/cache";
        match entries(fs, cache_root, 32) {
            Ok(names) => {
                for name in names.iter().filter(|n| n.starts_with("index")) {
                    let path = format!("{cache_root}/{name}");
                    let values = ["level", "type", "size", "shared_cpu_list"].map(|file| {
                        fs.read(&format!("{path}/{file}"))
                            .map(|s| s.trim().to_owned())
                            .unwrap_or_else(|_| "?".into())
                    });
                    row(&mut out, &format!("CPU · cache {name}"), format!("L{} {} {} / shared CPUs {}", values[0],values[1],values[2],values[3]), "visible cpu0 cache", &path, "仅列 cpu0 的缓存拓扑作为参考；不假设所有 CPU 相同。内存拷贝工作集若落在缓存中，不能当成 DRAM 带宽。");
                }
            }
            Err(e) => out.push(Metric::unavailable(
                Topic::Summary,
                "CPU · cache",
                cache_root,
                e,
            )),
        }
        file_row(
            fs,
            &mut out,
            "/sys/devices/system/node/online",
            "NUMA · 在线节点",
            "visible topology",
            "节点对应不同内存访问距离；进一步见 NUMA 页。",
        );
        match fs.read("/proc/meminfo") {
            Ok(text) => {
                for (key, value) in key_values(&text)
                    .filter(|(k, _)| ["MemTotal", "MemAvailable", "SwapTotal"].contains(k))
                {
                    let kib = value
                        .split_whitespace()
                        .next()
                        .and_then(|v| v.parse::<f64>().ok());
                    row(&mut out, &format!("内存 · {key}"), kib.map(|v| format!("{:.2} GiB", v/1048576.0)).unwrap_or_else(|| value.into()), "proc view; not cgroup-local", "/proc/meminfo", "系统可见内存，不等于容器可用额度。当前可用量还受 cgroup 以及其他任务影响。");
                }
            }
            Err(e) => out.push(Metric::unavailable(
                Topic::Summary,
                "内存 · 系统容量",
                "/proc/meminfo",
                e,
            )),
        }
        for (root, limit, network) in [
            ("/sys/class/net", 64, true),
            ("/sys/class/block", 128, false),
        ] {
            match entries(fs, root, limit) {
                Ok(names) => {
                    for name in names {
                        let base = format!("{root}/{name}");
                        if network {
                            let read = |file: &str| {
                                fs.read(&format!("{base}/{file}"))
                                    .map(|s| s.trim().to_owned())
                                    .unwrap_or_else(|_| "N/A".into())
                            };
                            let speed = read("speed");
                            let speed = if speed.starts_with('-') {
                                "unknown".into()
                            } else {
                                speed
                            };
                            row(&mut out, &format!("网络 · {name}"), format!("{} / MTU {} / link {} Mb/s",read("operstate"),read("mtu"),speed), "current net namespace", &base, "链路标称速率不是实测吞吐；虚拟接口可能不提供速率。TCP 回环测试不会经过物理网卡。");
                        } else {
                            // Partitions and pseudo devices remain visible, explicitly labelled.
                            let sectors = fs
                                .read(&format!("{base}/size"))
                                .ok()
                                .and_then(|s| s.trim().parse::<u64>().ok());
                            let capacity = sectors
                                .map(|n| format!("{:.2} GiB", n as f64 * 512.0 / 1073741824.0))
                                .unwrap_or_else(|| "N/A".into());
                            let kind = if fs.path(&format!("{base}/partition")).exists() {
                                "partition"
                            } else {
                                "device"
                            };
                            let rotational = fs
                                .read(&format!("{base}/queue/rotational"))
                                .map(|s| s.trim().to_owned())
                                .unwrap_or_else(|_| "N/A".into());
                            let scheduler = fs
                                .read(&format!("{base}/queue/scheduler"))
                                .map(|s| s.trim().to_owned())
                                .unwrap_or_else(|_| "N/A".into());
                            row(&mut out, &format!("存储 · {name}"), format!("{capacity} / {kind} / rotational={rotational} / {scheduler}"), "visible block topology", &base, "可见设备容量和队列策略；rotational=0 不足以证明是本地 NVMe。分区和映射设备不可重复求和，也不保证容器能访问设备。");
                        }
                    }
                }
                Err(e) => out.push(Metric::unavailable(
                    Topic::Summary,
                    if network {
                        "网络 · 配置"
                    } else {
                        "存储 · 配置"
                    },
                    root,
                    e,
                )),
            }
        }
        match fs.read("/proc/self/mountinfo") {
            Ok(text) => {
                for line in text.lines() {
                    if let Some((left, right)) = line.split_once(" - ") {
                        if left.split_whitespace().nth(4) == Some("/") {
                            row(&mut out, "存储 · 根文件系统", right.split_whitespace().next().unwrap_or("unknown"), "current mount namespace", "/proc/self/mountinfo", "overlay/tmpfs 上的临时文件测试不能推断底层物理磁盘性能；测试目录可能处于另一个文件系统。");
                        }
                    }
                }
            }
            Err(e) => out.push(Metric::unavailable(
                Topic::Summary,
                "存储 · 根文件系统",
                "/proc/self/mountinfo",
                e,
            )),
        }
        out
    }
}

/// Reuse already collected observations; do not invent a second cgroup resolver.
pub fn append_live_summary(metrics: &mut Vec<Metric>) {
    let mut extra = Vec::new();
    for metric in metrics.iter() {
        let label = if metric.name == "cpu busy" {
            Some("当前 · 系统 CPU busy")
        } else if metric.scope == "current process cgroup" {
            match metric.name.as_str() {
                "cpu.max" | "cpu.cfs_quota_us" | "cpu.cfs_period_us" => Some("容器 · CPU 配额"),
                "memory.current" | "memory.usage_in_bytes" => Some("容器 · 内存用量 bytes"),
                "memory.max" | "memory.limit_in_bytes" => Some("容器 · 内存上限 bytes"),
                _ => None,
            }
        } else {
            None
        };
        if let Some(label) = label {
            let mut copy = metric.clone();
            copy.topic = Topic::Summary;
            copy.name = label.into();
            extra.push(copy);
        }
    }
    if !extra.iter().any(|m| m.name == "容器 · 内存上限 bytes") {
        extra.push(Metric::unavailable(
            Topic::Summary,
            "容器 · 限额",
            "/proc/self/cgroup",
            "未采集到可映射的容器限制；不能用系统容量代替",
        ));
    }
    // Put current state and constraints ahead of long device lists.
    let position = metrics
        .iter()
        .position(|m| m.topic == Topic::Summary && m.name.starts_with("网络"))
        .unwrap_or(metrics.len());
    metrics.splice(position..position, extra);
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn counts_allowed_cpus_without_duplicate_ids() {
        assert_eq!(cpu_list_count("0-3,2,8,10-11"), Some(7));
        assert_eq!(cpu_list_count("3-1"), None);
        assert_eq!(cpu_list_count(""), None);
    }
    #[test]
    fn topology_uses_socket_core_pairs() {
        let text = "processor : 0\nphysical id : 0\ncore id : 0\n\nprocessor : 1\nphysical id : 0\ncore id : 0\n\nprocessor : 2\nphysical id : 1\ncore id : 0\n";
        assert_eq!(cpu_topology(text), (3, 2, 2));
    }
}
