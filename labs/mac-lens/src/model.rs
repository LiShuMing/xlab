use serde::Serialize;
use std::collections::HashMap;
use std::time::Instant;

#[derive(Clone, Debug, Default, Serialize)]
pub struct Gpu {
    pub active_percent: Option<f64>,
    pub frequency_mhz: Option<u32>,
    pub power_watts: Option<f64>,
    pub cpu_power_watts: Option<f64>,
    pub temperature_c: Option<f64>,
    pub reason: String,
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct Memory {
    pub total: u64,
    pub used: u64,
    pub available: u64,
    pub swap_used: u64,
    pub swap_total: u64,
    pub compressed: Option<u64>,
    pub swap_in_bps: Option<f64>,
    pub swap_out_bps: Option<f64>,
    pub pressure: Option<String>,
    pub native_reason: String,
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct Disk {
    pub device: String,
    pub mount: String,
    pub total: u64,
    pub available: u64,
    pub read_bps: Option<f64>,
    pub write_bps: Option<f64>,
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct Network {
    pub name: String,
    pub rx_bps: Option<f64>,
    pub tx_bps: Option<f64>,
    pub errors: u64,
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct Process {
    pub pid: u32,
    pub name: String,
    // One fully busy logical CPU = 100%; multithreaded processes may exceed 100%.
    pub cpu_percent: Option<f64>,
    pub memory: u64,
    pub read_bps: Option<f64>,
    pub write_bps: Option<f64>,
    pub candidate: bool,
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct Inference {
    pub connected: bool,
    pub reason: String,
    pub running: Option<f64>,
    pub waiting: Option<f64>,
    pub kv_percent: Option<f64>,
    pub prompt_tps: Option<f64>,
    pub generation_tps: Option<f64>,
    pub ttft_seconds: Option<f64>,
    pub tpot_seconds: Option<f64>,
    pub itl_seconds: Option<f64>,
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct Snapshot {
    pub schema_version: u32,
    pub sequence: u64,
    pub unix_ms: u128,
    pub sampling_ms: u128,
    pub cpu_model: String,
    pub cpu_percent: f64,
    pub cores: Vec<f64>,
    pub load_one: f64,
    pub gpu: Gpu,
    pub memory: Memory,
    pub disks: Vec<Disk>,
    pub networks: Vec<Network>,
    pub processes: Vec<Process>,
    pub inference: Inference,
    pub hints: Vec<String>,
}

// Difference cumulative counters over their actual observation interval, never
// over the configured polling interval. Reset/disappearance establishes a new
// baseline rather than producing an enormous or negative rate.
#[derive(Default)]
pub struct Rates {
    previous: HashMap<String, (f64, Instant)>,
}

impl Rates {
    pub fn observe(&mut self, key: &str, counter: f64, now: Instant) -> Option<f64> {
        if !counter.is_finite() || counter < 0.0 {
            self.previous.remove(key);
            return None;
        }
        let (old, at) = self.previous.insert(key.to_owned(), (counter, now))?;
        let elapsed = now.checked_duration_since(at)?.as_secs_f64();
        let delta = counter - old;
        let rate = delta / elapsed;
        (elapsed > 0.0 && delta >= 0.0 && rate.is_finite()).then_some(rate)
    }

    pub fn retain(&mut self, prefix: &str, present: &std::collections::HashSet<String>) {
        self.previous
            .retain(|key, _| !key.starts_with(prefix) || present.contains(key));
    }

    pub fn clear(&mut self) {
        self.previous.clear();
    }
}

pub fn finite(value: f64, min: f64, max: f64) -> Option<f64> {
    (value.is_finite() && (min..=max).contains(&value)).then_some(value)
}

pub fn safe_text(text: &str) -> String {
    text.chars().filter(|c| !c.is_control()).take(160).collect()
}

pub fn hints(s: &Snapshot) -> Vec<String> {
    let mut out = Vec::new();
    if matches!(s.memory.pressure.as_deref(), Some("warning" | "critical")) {
        out.push(
            "Memory pressure: reduce model/context/batch; inspect swap traffic, not RAM% alone."
                .into(),
        );
    }
    if s.memory.swap_in_bps.unwrap_or(0.0) + s.memory.swap_out_bps.unwrap_or(0.0) > 1024.0 * 1024.0
    {
        out.push(
            "Active swapping >1 MiB/s: memory contention is a candidate cause of inference stalls."
                .into(),
        );
    }
    if s.cpu_percent > 85.0 {
        out.push(
            "CPU busy >85%: check tokenization, prefill/CPU fallback and competing processes."
                .into(),
        );
    } else if s.cores.iter().any(|x| *x > 95.0) {
        out.push("One CPU core >95%: a serial feeder/tokenizer may limit throughput despite low CPU average.".into());
    }
    if s.gpu.active_percent.is_some_and(|v| v > 90.0) {
        out.push("GPU active >90%: accelerator is occupied; this does NOT distinguish compute vs memory bandwidth.".into());
    }
    if s.inference.waiting.is_some_and(|v| v > 0.0) {
        out.push("vLLM queue nonempty: compare GPU activity, KV cache and TTFT before changing concurrency.".into());
    }
    if s.inference.kv_percent.is_some_and(|v| v > 90.0) {
        out.push(
            "vLLM KV cache >90%: inspect context lengths, cache eviction and request queue.".into(),
        );
    }
    if s.disks
        .iter()
        .any(|d| d.total > 0 && d.available < d.total / 20)
    {
        out.push("Filesystem free <5%: leave space for model downloads, caches and swap.".into());
    }
    if out.is_empty() {
        out.push("No threshold crossed. Not proof of headroom; correlate request latency with resource history.".into());
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::Duration;

    #[test]
    fn rate_warmup_reset_and_actual_time() {
        let at = Instant::now();
        let mut rates = Rates::default();
        assert_eq!(rates.observe("a", 100.0, at), None);
        assert_eq!(
            rates.observe("a", 200.0, at + Duration::from_secs(2)),
            Some(50.0)
        );
        assert_eq!(rates.observe("a", 2.0, at + Duration::from_secs(3)), None);
        assert_eq!(
            rates.observe("a", 2.0, at + Duration::from_secs(4)),
            Some(0.0)
        );
        assert_eq!(rates.observe("a", f64::NAN, at), None);
        assert_eq!(rates.observe("a", 10.0, at), None);
        assert_eq!(rates.observe("a", 11.0, at), None);
    }

    #[test]
    fn absent_interfaces_do_not_leave_stale_baselines() {
        let mut rates = Rates::default();
        rates.observe("net:a", 100.0, Instant::now());
        rates.retain("net:", &Default::default());
        assert_eq!(rates.observe("net:a", 200.0, Instant::now()), None);
    }

    #[test]
    fn busy_gpu_is_not_claimed_to_be_compute_bound() {
        let mut s = Snapshot::default();
        s.gpu.active_percent = Some(98.0);
        assert!(hints(&s).join(" ").contains("does NOT distinguish"));
        assert_eq!(safe_text("a\x1b\n\rb"), "ab");
        assert_eq!(finite(f64::INFINITY, 0.0, 100.0), None);
    }
}
