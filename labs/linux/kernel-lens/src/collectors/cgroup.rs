use super::{Collector, LinuxFs};
use crate::model::{Metric, Topic};
use std::path::{Component, Path};
use std::time::Instant;

pub struct CgroupCollector;

#[derive(Debug, PartialEq, Eq)]
pub struct Group {
    pub version: u8,
    pub controller: String,
    pub directory: String,
}

fn unescape_mount(text: &str) -> String {
    text.replace("\\040", " ")
        .replace("\\011", "\t")
        .replace("\\012", "\n")
        .replace("\\134", "\\")
}

fn safe_path(path: &Path) -> bool {
    !path
        .components()
        .any(|part| matches!(part, Component::ParentDir))
}

/// Resolve the process membership against the mount's filesystem root, not a
/// hardcoded /sys/fs/cgroup path. Never silently substitute the mount root when
/// the requested group is outside the visible subtree.
pub fn resolve_groups(membership: &str, mountinfo: &str) -> Vec<Group> {
    let mut groups = Vec::new();
    for line in membership.lines() {
        let fields: Vec<_> = line.splitn(3, ':').collect();
        if fields.len() != 3 {
            continue;
        }
        let member = Path::new(fields[2]);
        if !member.is_absolute() || !safe_path(member) {
            continue;
        }
        for mount in mountinfo.lines() {
            let Some((left, right)) = mount.split_once(" - ") else {
                continue;
            };
            let left: Vec<_> = left.split_whitespace().collect();
            let right: Vec<_> = right.split_whitespace().collect();
            if left.len() < 6 || right.len() < 3 {
                continue;
            }
            let version = match right[0] {
                "cgroup2" if fields[1].is_empty() => 2,
                "cgroup" if !fields[1].is_empty() => 1,
                _ => continue,
            };
            let controllers: Vec<_> = fields[1].split(',').collect();
            if version == 1
                && !controllers
                    .iter()
                    .all(|c| right[2].split(',').any(|m| m == *c))
            {
                continue;
            }
            let root = unescape_mount(left[3]);
            let point = unescape_mount(left[4]);
            if !safe_path(Path::new(&root)) || !safe_path(Path::new(&point)) {
                continue;
            }
            let Ok(relative) = member.strip_prefix(Path::new(&root)) else {
                continue;
            };
            let directory = Path::new(&point)
                .join(relative)
                .to_string_lossy()
                .into_owned();
            for controller in &controllers {
                let group = Group {
                    version,
                    controller: (*controller).into(),
                    directory: directory.clone(),
                };
                if !groups.contains(&group) {
                    groups.push(group);
                }
            }
        }
    }
    groups
}

impl Collector for CgroupCollector {
    fn collect(&mut self, fs: &LinuxFs, _now: Instant) -> Vec<Metric> {
        let mut out = Vec::new();
        let membership = match fs.read("/proc/self/cgroup") {
            Ok(text) => text,
            Err(e) => {
                return vec![Metric::unavailable(
                    Topic::Overview,
                    "cgroup membership",
                    "/proc/self/cgroup",
                    e,
                )]
            }
        };
        for line in membership.lines() {
            out.push(Metric::new(
                Topic::Overview,
                "cgroup membership",
                line,
                "",
                "current process",
                "/proc/self/cgroup",
                "当前进程的控制组路径；v1 各控制器可能不同，v2 使用统一层级。",
            ));
        }
        let mountinfo = match fs.read("/proc/self/mountinfo") {
            Ok(text) => text,
            Err(e) => {
                out.push(Metric::unavailable(
                    Topic::Overview,
                    "cgroup mounts",
                    "/proc/self/mountinfo",
                    e,
                ));
                return out;
            }
        };
        let groups = resolve_groups(&membership, &mountinfo);
        if groups.is_empty() {
            out.push(Metric::unavailable(
                Topic::Overview,
                "cgroup metrics",
                "/proc/self/mountinfo",
                "no matching visible cgroup mount; membership may be outside the mounted subtree",
            ));
        }
        for group in groups {
            let files: Vec<(&str, Topic)> = if group.version == 2 {
                vec![
                    ("cpu.max", Topic::Cpu),
                    ("cpu.stat", Topic::Cpu),
                    ("cpu.pressure", Topic::Cpu),
                    ("cpuset.cpus.effective", Topic::Cpu),
                    ("cpuset.mems.effective", Topic::Numa),
                    ("memory.current", Topic::Memory),
                    ("memory.max", Topic::Memory),
                    ("memory.events", Topic::Memory),
                    ("memory.pressure", Topic::Memory),
                    ("io.stat", Topic::Storage),
                    ("io.pressure", Topic::Storage),
                ]
            } else {
                match group.controller.as_str() {
                    "cpu" => vec![
                        ("cpu.cfs_quota_us", Topic::Cpu),
                        ("cpu.cfs_period_us", Topic::Cpu),
                        ("cpu.stat", Topic::Cpu),
                    ],
                    "cpuacct" => vec![("cpuacct.usage", Topic::Cpu)],
                    "cpuset" => vec![("cpuset.cpus", Topic::Cpu), ("cpuset.mems", Topic::Numa)],
                    "memory" => vec![
                        ("memory.usage_in_bytes", Topic::Memory),
                        ("memory.limit_in_bytes", Topic::Memory),
                        ("memory.failcnt", Topic::Memory),
                    ],
                    "blkio" => vec![("blkio.throttle.io_service_bytes", Topic::Storage)],
                    _ => Vec::new(),
                }
            };
            for (file, topic) in files {
                let path = format!("{}/{file}", group.directory.trim_end_matches('/'));
                match fs.read(&path) {
                    Ok(text) => {
                        let explanation = match file {
                            "cpu.max" => "quota period，单位微秒；quota/period 是 CPU 时间配额折算的核数，max 表示本层不设限。祖先可能有更严限制。",
                            "cpu.stat" => "累计 CPU 使用和限流计数。v2 *_usec 是微秒，v1 throttled_time 是纳秒；nr_throttled 是被限流周期数。",
                            "cpuacct.usage" => "cgroup v1 累计 CPU 时间，单位纳秒。",
                            "cpu.cfs_quota_us" => "每周期可用 CPU 时间，单位微秒；-1 表示本层不设限。与 cpu.cfs_period_us 相除得到配额核数。",
                            "cpu.cfs_period_us" => "CPU 配额周期，单位微秒。祖先配额和 cpuset 仍可能限制有效资源。",
                            name if name.contains("pressure") => "所选控制组的 PSI：some/full avg10/60/300 为停顿时间百分比，total 为累计微秒。",
                            name if name.contains("cpuset") => "允许的 CPU/NUMA 节点列表；v1 空值可能继承祖先。本工具不遍历祖先；进程有效许可见环境页。",
                            name if name.contains("io") => "所选控制组块 I/O 累计计数；设备用 major:minor 标识。不是延迟或文件系统容量。",
                            name if name.contains("events") || name.contains("failcnt") => "累计触达限制、OOM 等事件；应观察增量，不能仅凭历史非零判断当前异常。",
                            _ => "cgroup 内存字节数。max 或很大的 v1 limit 常表示本层不限；祖先可能更严。与 /proc/meminfo 口径不同。",
                        };
                        if text.trim().is_empty() {
                            out.push(Metric::new(
                                topic,
                                file,
                                "empty / inherited or no activity",
                                "",
                                "current process cgroup",
                                &path,
                                explanation,
                            ));
                        } else {
                            for line in text.lines() {
                                out.push(Metric::new(
                                    topic,
                                    file,
                                    line,
                                    "",
                                    "current process cgroup",
                                    &path,
                                    explanation,
                                ));
                            }
                        }
                    }
                    Err(e) => out.push(Metric::unavailable(topic, file, &path, e)),
                }
            }
        }
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn resolves_v2_subtree_and_namespace_root() {
        let mounts = "31 20 0:27 /slice /sys/fs/cgroup rw - cgroup2 cgroup rw";
        assert_eq!(
            resolve_groups("0::/slice/app", mounts)[0].directory,
            "/sys/fs/cgroup/app"
        );
        assert!(resolve_groups("0::/elsewhere", mounts).is_empty());
        assert_eq!(
            resolve_groups("0::/", "31 20 0:27 / /sys/fs/cgroup rw - cgroup2 cgroup rw")[0]
                .directory,
            "/sys/fs/cgroup/"
        );
    }
    #[test]
    fn resolves_v1_combined_controllers_and_escaped_mountpoint() {
        let groups = resolve_groups(
            "3:cpu,cpuacct:/team/job",
            "31 20 0:27 /team /cg\\040space rw - cgroup cgroup rw,cpu,cpuacct",
        );
        assert_eq!(groups.len(), 2);
        assert_eq!(groups[0].directory, "/cg space/job");
        assert!(resolve_groups(
            "3:memory:/team/job",
            "31 20 0:27 / /cg rw - cgroup cgroup rw,cpu"
        )
        .is_empty());
    }
    #[test]
    fn rejects_parent_traversal_and_prefix_collisions() {
        let mounts = "31 20 0:27 /team /cg rw - cgroup2 cgroup rw";
        assert!(resolve_groups("0::/team/../escape", mounts).is_empty());
        assert!(resolve_groups("0::/teammate/job", mounts).is_empty());
    }
}
