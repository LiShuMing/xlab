mod cgroup;
mod inventory;
mod procfs;
mod sysfs;

use crate::model::{Metric, Snapshot};
pub use cgroup::CgroupCollector;
pub use procfs::ProcCollector;
use std::fs::File;
use std::io::{self, Read};
use std::path::{Path, PathBuf};
use std::time::{Instant, SystemTime, UNIX_EPOCH};
pub use sysfs::{CapabilityCollector, SysCollector};

/// The same bounded filesystem reader serves live proc/sys data and test fixtures.
#[derive(Clone)]
pub struct LinuxFs {
    root: PathBuf,
}

impl LinuxFs {
    pub fn new(root: impl Into<PathBuf>) -> Self {
        Self { root: root.into() }
    }

    pub fn path(&self, absolute: &str) -> PathBuf {
        self.root.join(absolute.trim_start_matches('/'))
    }

    pub fn read(&self, absolute: &str) -> io::Result<String> {
        const LIMIT: u64 = 4 * 1024 * 1024;
        let mut text = String::new();
        File::open(self.path(absolute))?
            .take(LIMIT + 1)
            .read_to_string(&mut text)?;
        if text.len() as u64 > LIMIT {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "source exceeds 4 MiB read limit",
            ));
        }
        Ok(text)
    }

    pub fn link(&self, absolute: &str) -> io::Result<PathBuf> {
        std::fs::read_link(self.path(absolute))
    }
}

/// Collectors retain their own baselines and emit provenance-bearing observations.
/// Implementations must return bounded work; unavailable sources emit N/A rows.
pub trait Collector {
    fn collect(&mut self, fs: &LinuxFs, now: Instant) -> Vec<Metric>;
}

pub struct Kernel {
    fs: LinuxFs,
    collectors: Vec<Box<dyn Collector>>,
    sequence: u64,
}

impl Kernel {
    pub fn live() -> Self {
        Self::new(LinuxFs::new(Path::new("/")))
    }

    pub fn new(fs: LinuxFs) -> Self {
        Self {
            fs,
            collectors: vec![
                Box::new(inventory::InventoryCollector),
                Box::new(ProcCollector::default()),
                Box::new(SysCollector),
                Box::new(CgroupCollector),
                Box::new(CapabilityCollector),
            ],
            sequence: 0,
        }
    }

    pub fn register(&mut self, collector: Box<dyn Collector>) {
        self.collectors.push(collector);
    }

    pub fn sample(&mut self) -> Snapshot {
        let start = Instant::now();
        let mut metrics = Vec::new();
        for collector in &mut self.collectors {
            metrics.extend(collector.collect(&self.fs, Instant::now()));
        }
        inventory::append_live_summary(&mut metrics);
        self.sequence += 1;
        Snapshot {
            schema_version: 1,
            sequence: self.sequence,
            unix_time_ms: SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap_or_default()
                .as_millis(),
            collection_ms: start.elapsed().as_millis(),
            metrics,
        }
    }
}

pub(crate) fn key_values(text: &str) -> impl Iterator<Item = (&str, &str)> {
    text.lines().filter_map(|line| {
        let (key, value) = line.split_once(char::is_whitespace)?;
        Some((key.trim_end_matches(':'), value.trim()))
    })
}
