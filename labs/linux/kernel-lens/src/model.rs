use serde::Serialize;
use std::collections::HashMap;
use std::time::{Duration, Instant};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
pub enum Topic {
    Summary,
    Overview,
    Cpu,
    Numa,
    Memory,
    Network,
    Storage,
    Capabilities,
    Benchmark,
}

impl Topic {
    pub const ALL: [Self; 9] = [
        Self::Summary,
        Self::Overview,
        Self::Cpu,
        Self::Numa,
        Self::Memory,
        Self::Network,
        Self::Storage,
        Self::Capabilities,
        Self::Benchmark,
    ];

    pub fn title(self) -> &'static str {
        match self {
            Self::Summary => "机器总览",
            Self::Benchmark => "Benchmark",
            Self::Overview => "环境/容器",
            Self::Cpu => "CPU/调度",
            Self::Numa => "NUMA",
            Self::Memory => "内存",
            Self::Network => "网络",
            Self::Storage => "存储",
            Self::Capabilities => "perf/BPF",
        }
    }

    pub fn lesson(self) -> &'static str {
        match self {
            Self::Summary => "先核对机器可见配置、进程许可和容器限额，再比较性能；共享负载、CPU 迁移和缓存都会影响测试。",
            Self::Benchmark => "基准只衡量列出的工作负载；单线程、缓存拷贝、回环和文件缓存测试不能替代整机性能结论。",
            Self::Overview => "namespace 隔离可见资源；cgroup 限制资源。容器里的 /proc 并不都按容器统计。",
            Self::Cpu => "CPU busy 来自 tick 差分；load 包含可运行和不可中断睡眠任务，不等于 CPU 使用率。ctxt 是切换次数，不是调度延迟。",
            Self::Numa => "NUMA：不同 CPU 访问各内存节点的成本不同。拓扑可见不代表当前容器获准使用所有节点。",
            Self::Memory => "MemAvailable 是内核估计的可用内存；PSI 是任务因资源不足而停顿的时间比例，不是利用率。",
            Self::Network => "网卡字节计数属于当前网络 namespace。吞吐不代表 TCP 延迟；丢包计数需结合具体接口和协议分析。",
            Self::Storage => "diskstats 是块设备层累计计数；512 字节扇区用于统计，和物理扇区大小无关。设备可能包含分区和叠加层，不能简单相加。",
            Self::Capabilities => "perf 使用内核性能事件；BPF 是内核中的受验证程序。文件或工具存在仅说明线索，不证明可以加载程序或访问事件。",
        }
    }

    pub fn commands(self) -> &'static str {
        match self {
            Self::Summary => "lscpu; free -h; lsblk; ip -s link",
            Self::Benchmark => "选择测试后按 r 运行；推荐 cargo run --release --locked",
            Self::Overview => "cat /proc/self/cgroup; lsns; systemd-cgls",
            Self::Cpu => {
                "vmstat 1; pidstat -w 1; perf stat -e task-clock,context-switches -- sleep 1"
            }
            Self::Numa => "lscpu -e=CPU,NODE,SOCKET,CORE; numactl --hardware; numastat -p <PID>",
            Self::Memory => "free -h; cat /proc/pressure/memory; pidstat -r 1",
            Self::Network => "ip -s link; ss -s; nstat -az",
            Self::Storage => "iostat -dx 1; lsblk -o NAME,TYPE,SIZE,MOUNTPOINTS; findmnt",
            Self::Capabilities => "perf list; bpftool feature probe unprivileged; bpftrace --info",
        }
    }
}

fn visible(text: String) -> String {
    text.chars()
        .map(|c| if c.is_control() { '�' } else { c })
        .collect()
}

#[derive(Clone, Debug, Serialize)]
pub enum State {
    Ready,
    Warming,
    Unavailable,
}

#[derive(Clone, Debug, Serialize)]
pub struct Metric {
    pub topic: Topic,
    pub name: String,
    pub value: String,
    pub unit: String,
    pub scope: String,
    pub source: String,
    pub explanation: String,
    pub state: State,
}

impl Metric {
    pub fn new(
        topic: Topic,
        name: impl Into<String>,
        value: impl Into<String>,
        unit: &str,
        scope: &str,
        source: impl Into<String>,
        explanation: &str,
    ) -> Self {
        Self {
            topic,
            name: visible(name.into()),
            value: visible(value.into()),
            unit: unit.into(),
            scope: scope.into(),
            source: visible(source.into()),
            explanation: explanation.into(),
            state: State::Ready,
        }
    }

    pub fn unavailable(topic: Topic, name: &str, source: &str, error: impl ToString) -> Self {
        let mut metric = Self::new(
            topic,
            name,
            "N/A",
            "",
            "unknown",
            source,
            &error.to_string(),
        );
        metric.state = State::Unavailable;
        metric
    }
}

#[derive(Default)]
pub struct Rates {
    previous: HashMap<String, (u64, Instant)>,
}

impl Rates {
    pub fn sample(&mut self, key: &str, value: u64, now: Instant) -> Option<f64> {
        let old = self.previous.insert(key.into(), (value, now))?;
        rate(old.0, value, now.saturating_duration_since(old.1))
    }
}

pub fn rate(before: u64, after: u64, elapsed: Duration) -> Option<f64> {
    let delta = after.checked_sub(before)?;
    let seconds = elapsed.as_secs_f64();
    (seconds > 0.0).then(|| delta as f64 / seconds)
}

#[derive(Serialize)]
pub struct Snapshot {
    pub schema_version: u32,
    pub sequence: u64,
    pub unix_time_ms: u128,
    pub collection_ms: u128,
    pub metrics: Vec<Metric>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn counter_reset_and_initial_sample_are_not_zero_activity() {
        let mut rates = Rates::default();
        let now = Instant::now();
        assert_eq!(rates.sample("rx", 100, now), None);
        assert_eq!(
            rates.sample("rx", 150, now + Duration::from_secs(2)),
            Some(25.0)
        );
        assert_eq!(rates.sample("rx", 1, now + Duration::from_secs(3)), None);
        assert_eq!(rate(1, 2, Duration::ZERO), None);
    }
}
