//! A small, dependency-free implementation of Hybrid Grace Hash Join.
//!
//! The implementation intentionally favors visible algorithm boundaries over raw
//! performance. In particular, it spills *logical rows* rather than serializing a
//! `HashMap`, and it rebuilds a partition-local hash table for every restored
//! partition.

use std::collections::HashMap;
use std::fmt;
use std::io::{self, Read, Write};

use spill_io::{SpillCodec, SpillDirectory, SpillFile, SpillReader, SpillWriter};

/// A row on either side of the join.
///
/// `None` follows normal SQL equality semantics: NULL does not equal NULL and is
/// therefore skipped by this inner join implementation.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Row {
    pub key: Option<u64>,
    pub payload: String,
}

impl Row {
    pub fn new(key: u64, payload: impl Into<String>) -> Self {
        Self {
            key: Some(key),
            payload: payload.into(),
        }
    }

    pub fn null(payload: impl Into<String>) -> Self {
        Self {
            key: None,
            payload: payload.into(),
        }
    }
}

/// One output row from an inner join.
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct JoinedRow {
    pub key: u64,
    pub build_payload: String,
    pub probe_payload: String,
}

/// Configuration for the learning implementation.
#[derive(Clone, Debug)]
pub struct JoinConfig {
    /// Maximum number of build rows in one local hash table.
    ///
    /// Real engines budget bytes and include buckets, payloads and buffers. A row
    /// count keeps the state transitions deterministic and easy to reproduce.
    pub memory_budget_rows: usize,
    /// Number of children created at each partitioning level. Must be a power of two.
    pub partitions: usize,
    /// Maximum number of recursive repartition steps after the initial partition.
    pub max_repartition_depth: usize,
}

impl Default for JoinConfig {
    fn default() -> Self {
        Self {
            memory_budget_rows: 4,
            partitions: 4,
            max_repartition_depth: 3,
        }
    }
}

impl JoinConfig {
    fn validate(&self) -> io::Result<()> {
        if self.memory_budget_rows == 0 {
            return Err(invalid_input(
                "memory_budget_rows must be greater than zero",
            ));
        }
        if self.partitions < 2 || !self.partitions.is_power_of_two() {
            return Err(invalid_input(
                "partitions must be a power of two and at least two",
            ));
        }

        let bits = self.partitions.trailing_zeros() as usize;
        if (self.max_repartition_depth + 1).saturating_mul(bits) > u64::BITS as usize {
            return Err(invalid_input(
                "partition bits exceed the width of the 64-bit hash",
            ));
        }
        Ok(())
    }
}

/// Observable counters for the external path.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct JoinStats {
    pub build_rows: usize,
    pub probe_rows: usize,
    pub output_rows: usize,
    pub null_build_rows: usize,
    pub null_probe_rows: usize,
    /// Counts every logical row write. A row written again during repartition is
    /// counted again, just like physical spill I/O volume.
    pub spilled_build_rows: usize,
    pub spilled_probe_rows: usize,
    pub spilled_build_bytes: u64,
    pub spilled_probe_bytes: u64,
    pub restored_partitions: usize,
    pub repartitions: usize,
    pub max_partition_build_rows: usize,
    pub max_depth: usize,
    pub hybrid_partition_kept: bool,
}

/// High-level state transitions emitted by the join.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum JoinEvent {
    InMemoryBuild {
        rows: usize,
    },
    InitialPartitioning {
        partitions: usize,
    },
    HybridPartitionKept {
        partition: usize,
        build_rows: usize,
    },
    HybridPartitionRevoked {
        partition: usize,
        build_rows: usize,
    },
    ImmediateProbe {
        partition: usize,
        probe_rows: usize,
    },
    Restore {
        level: usize,
        partition: usize,
        build_rows: usize,
        probe_rows: usize,
    },
    Repartition {
        from_level: usize,
        partition: usize,
        build_rows: usize,
        child_partitions: usize,
    },
}

impl fmt::Display for JoinEvent {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InMemoryBuild { rows } => {
                write!(f, "build one in-memory hash table ({rows} rows)")
            }
            Self::InitialPartitioning { partitions } => {
                write!(f, "partition build/probe with the same hash into {partitions} buckets")
            }
            Self::HybridPartitionKept {
                partition,
                build_rows,
            } => write!(
                f,
                "keep bucket {partition} in memory for Hybrid join ({build_rows} build rows)"
            ),
            Self::HybridPartitionRevoked {
                partition,
                build_rows,
            } => write!(
                f,
                "bucket {partition} exceeded the budget; spill its {build_rows} logical rows"
            ),
            Self::ImmediateProbe {
                partition,
                probe_rows,
            } => write!(
                f,
                "probe in-memory bucket {partition} immediately ({probe_rows} probe rows)"
            ),
            Self::Restore {
                level,
                partition,
                build_rows,
                probe_rows,
            } => write!(
                f,
                "restore L{level} bucket {partition}: rebuild {build_rows} build rows, probe {probe_rows} rows"
            ),
            Self::Repartition {
                from_level,
                partition,
                build_rows,
                child_partitions,
            } => write!(
                f,
                "L{from_level} bucket {partition} still has {build_rows} build rows; repartition both sides into {child_partitions} children"
            ),
        }
    }
}

/// Complete result including data, counters and a human-readable execution trace.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct JoinResult {
    pub rows: Vec<JoinedRow>,
    pub stats: JoinStats,
    pub events: Vec<JoinEvent>,
}

/// Execute an inner Hybrid Grace Hash Join.
///
/// The fast path builds one in-memory table. Otherwise bucket zero is retained
/// while it fits, all other buckets are spilled, and oversized restored buckets
/// are recursively repartitioned with later bits from the same stable hash.
pub fn hybrid_grace_hash_join(
    build: &[Row],
    probe: &[Row],
    config: &JoinConfig,
) -> io::Result<JoinResult> {
    config.validate()?;

    let non_null_build_rows = build.iter().filter(|row| row.key.is_some()).count();
    let mut stats = JoinStats {
        build_rows: build.len(),
        probe_rows: probe.len(),
        null_build_rows: build.len() - non_null_build_rows,
        null_probe_rows: probe.iter().filter(|row| row.key.is_none()).count(),
        ..JoinStats::default()
    };
    let mut events = Vec::new();
    let mut output = Vec::new();

    if non_null_build_rows <= config.memory_budget_rows {
        events.push(JoinEvent::InMemoryBuild {
            rows: non_null_build_rows,
        });
        let table = build_hash_table(build.iter().filter(|row| row.key.is_some()).cloned());
        probe_hash_table(
            &table,
            probe.iter().filter(|row| row.key.is_some()),
            &mut output,
        );
        stats.output_rows = output.len();
        return Ok(JoinResult {
            rows: output,
            stats,
            events,
        });
    }

    events.push(JoinEvent::InitialPartitioning {
        partitions: config.partitions,
    });
    let mut workspace = SpillDirectory::new("grace-hash-join")?;
    let initial = partition_initial(
        build,
        probe,
        config,
        &mut workspace,
        &mut output,
        &mut stats,
        &mut events,
    )?;

    for task in initial {
        process_partition(
            task,
            config,
            &mut workspace,
            &mut output,
            &mut stats,
            &mut events,
        )?;
    }

    stats.output_rows = output.len();
    Ok(JoinResult {
        rows: output,
        stats,
        events,
    })
}

#[derive(Debug)]
struct PartitionTask {
    build_file: SpillFile,
    probe_file: SpillFile,
    build_rows: usize,
    probe_rows: usize,
    level: usize,
    partition: usize,
}

#[allow(clippy::too_many_arguments)]
fn partition_initial(
    build: &[Row],
    probe: &[Row],
    config: &JoinConfig,
    workspace: &mut SpillDirectory,
    output: &mut Vec<JoinedRow>,
    stats: &mut JoinStats,
    events: &mut Vec<JoinEvent>,
) -> io::Result<Vec<PartitionTask>> {
    let files = create_partition_files(workspace, config.partitions, 0)?;
    let mut build_writers = create_writers(files.iter().map(|pair| &pair.0))?;
    let mut build_counts = vec![0_usize; config.partitions];
    let mut resident_rows = Vec::new();
    let mut resident = true;

    for row in build.iter().filter(|row| row.key.is_some()) {
        let partition = partition_for(row.key.expect("filtered NULL"), 0, config.partitions);
        build_counts[partition] += 1;
        stats.max_partition_build_rows =
            stats.max_partition_build_rows.max(build_counts[partition]);

        if partition == 0 && resident {
            resident_rows.push(row.clone());
            if resident_rows.len() > config.memory_budget_rows {
                events.push(JoinEvent::HybridPartitionRevoked {
                    partition: 0,
                    build_rows: resident_rows.len(),
                });
                for resident_row in resident_rows.drain(..) {
                    write_spilled_row(&mut build_writers[0], &resident_row, true, stats)?;
                }
                resident = false;
            }
        } else {
            write_spilled_row(&mut build_writers[partition], row, true, stats)?;
        }
    }
    finish_writers(build_writers)?;

    let resident_table = if resident {
        stats.hybrid_partition_kept = true;
        events.push(JoinEvent::HybridPartitionKept {
            partition: 0,
            build_rows: resident_rows.len(),
        });
        Some(build_hash_table(resident_rows))
    } else {
        None
    };

    let mut probe_writers = create_writers(files.iter().map(|pair| &pair.1))?;
    let mut probe_counts = vec![0_usize; config.partitions];
    let mut immediate_probe_rows = 0;

    for row in probe.iter().filter(|row| row.key.is_some()) {
        let partition = partition_for(row.key.expect("filtered NULL"), 0, config.partitions);
        probe_counts[partition] += 1;
        if partition == 0 {
            if let Some(table) = resident_table.as_ref() {
                probe_one(table, row, output);
                immediate_probe_rows += 1;
                continue;
            }
        }
        write_spilled_row(&mut probe_writers[partition], row, false, stats)?;
    }
    finish_writers(probe_writers)?;

    if resident_table.is_some() {
        events.push(JoinEvent::ImmediateProbe {
            partition: 0,
            probe_rows: immediate_probe_rows,
        });
    }

    let mut tasks = Vec::new();
    for (partition, (build_file, probe_file)) in files.into_iter().enumerate() {
        if partition == 0 && resident_table.is_some() {
            continue;
        }
        if build_counts[partition] == 0 {
            continue;
        }
        tasks.push(PartitionTask {
            build_file,
            probe_file,
            build_rows: build_counts[partition],
            probe_rows: probe_counts[partition],
            level: 0,
            partition,
        });
    }
    Ok(tasks)
}

#[allow(clippy::too_many_arguments)]
fn process_partition(
    task: PartitionTask,
    config: &JoinConfig,
    workspace: &mut SpillDirectory,
    output: &mut Vec<JoinedRow>,
    stats: &mut JoinStats,
    events: &mut Vec<JoinEvent>,
) -> io::Result<()> {
    stats.max_partition_build_rows = stats.max_partition_build_rows.max(task.build_rows);
    stats.max_depth = stats.max_depth.max(task.level);

    if task.build_rows <= config.memory_budget_rows {
        let table = load_hash_table(&task.build_file)?;
        probe_spill_file(&table, &task.probe_file, output)?;
        stats.restored_partitions += 1;
        events.push(JoinEvent::Restore {
            level: task.level,
            partition: task.partition,
            build_rows: task.build_rows,
            probe_rows: task.probe_rows,
        });
        return Ok(());
    }

    if task.level >= config.max_repartition_depth {
        return Err(io::Error::new(
            io::ErrorKind::OutOfMemory,
            format!(
                "L{} bucket {} has {} build rows, above the {}-row budget after {} repartitions; likely skew or too many duplicate keys",
                task.level,
                task.partition,
                task.build_rows,
                config.memory_budget_rows,
                config.max_repartition_depth
            ),
        ));
    }

    events.push(JoinEvent::Repartition {
        from_level: task.level,
        partition: task.partition,
        build_rows: task.build_rows,
        child_partitions: config.partitions,
    });
    stats.repartitions += 1;

    let child_level = task.level + 1;
    let files = create_partition_files(workspace, config.partitions, child_level)?;
    let mut build_writers = create_writers(files.iter().map(|pair| &pair.0))?;
    let mut probe_writers = create_writers(files.iter().map(|pair| &pair.1))?;
    let mut build_counts = vec![0_usize; config.partitions];
    let mut probe_counts = vec![0_usize; config.partitions];

    let mut build_reader = SpillReader::open(&task.build_file, RowCodec)?;
    while let Some(row) = build_reader.read_next()? {
        let partition = partition_for(
            row.key.expect("spill files contain no NULL keys"),
            child_level,
            config.partitions,
        );
        build_counts[partition] += 1;
        write_spilled_row(&mut build_writers[partition], &row, true, stats)?;
    }
    let mut probe_reader = SpillReader::open(&task.probe_file, RowCodec)?;
    while let Some(row) = probe_reader.read_next()? {
        let partition = partition_for(
            row.key.expect("spill files contain no NULL keys"),
            child_level,
            config.partitions,
        );
        probe_counts[partition] += 1;
        write_spilled_row(&mut probe_writers[partition], &row, false, stats)?;
    }
    finish_writers(build_writers)?;
    finish_writers(probe_writers)?;

    for (partition, (build_file, probe_file)) in files.into_iter().enumerate() {
        if build_counts[partition] == 0 {
            continue;
        }
        process_partition(
            PartitionTask {
                build_file,
                probe_file,
                build_rows: build_counts[partition],
                probe_rows: probe_counts[partition],
                level: child_level,
                partition,
            },
            config,
            workspace,
            output,
            stats,
            events,
        )?;
    }
    Ok(())
}

type BuildTable = HashMap<u64, Vec<Row>>;

fn build_hash_table(rows: impl IntoIterator<Item = Row>) -> BuildTable {
    let mut table = BuildTable::new();
    for row in rows {
        let key = row.key.expect("hash table contains no NULL keys");
        table.entry(key).or_default().push(row);
    }
    table
}

fn probe_hash_table<'a>(
    table: &BuildTable,
    probe: impl Iterator<Item = &'a Row>,
    output: &mut Vec<JoinedRow>,
) {
    for row in probe {
        probe_one(table, row, output);
    }
}

fn probe_one(table: &BuildTable, probe: &Row, output: &mut Vec<JoinedRow>) {
    let Some(key) = probe.key else {
        return;
    };
    let Some(matches) = table.get(&key) else {
        return;
    };
    for build in matches {
        output.push(JoinedRow {
            key,
            build_payload: build.payload.clone(),
            probe_payload: probe.payload.clone(),
        });
    }
}

fn load_hash_table(file: &SpillFile) -> io::Result<BuildTable> {
    let mut table = BuildTable::new();
    let mut reader = SpillReader::open(file, RowCodec)?;
    while let Some(row) = reader.read_next()? {
        let key = row.key.expect("spill files contain no NULL keys");
        table.entry(key).or_default().push(row);
    }
    Ok(table)
}

fn probe_spill_file(
    table: &BuildTable,
    file: &SpillFile,
    output: &mut Vec<JoinedRow>,
) -> io::Result<()> {
    let mut reader = SpillReader::open(file, RowCodec)?;
    while let Some(row) = reader.read_next()? {
        probe_one(table, &row, output);
    }
    Ok(())
}

/// A deterministic finalizer makes the same key land in the same partition on
/// both sides and across processes. `DefaultHasher` is deliberately not used.
fn stable_hash(key: u64) -> u64 {
    let mut value = key.wrapping_add(0x9e37_79b9_7f4a_7c15);
    value = (value ^ (value >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
    value = (value ^ (value >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
    value ^ (value >> 31)
}

fn partition_for(key: u64, level: usize, partitions: usize) -> usize {
    let bits = partitions.trailing_zeros() as usize;
    let shift = level * bits;
    ((stable_hash(key) >> shift) as usize) & (partitions - 1)
}

fn create_partition_files(
    directory: &mut SpillDirectory,
    partitions: usize,
    level: usize,
) -> io::Result<Vec<(SpillFile, SpillFile)>> {
    (0..partitions)
        .map(|partition| {
            Ok((
                directory.create_file(&format!("level-{level}-build-{partition}"))?,
                directory.create_file(&format!("level-{level}-probe-{partition}"))?,
            ))
        })
        .collect()
}

fn create_writers<'a>(
    files: impl Iterator<Item = &'a SpillFile>,
) -> io::Result<Vec<SpillWriter<Row, RowCodec>>> {
    files
        .map(|file| SpillWriter::create(file, RowCodec))
        .collect()
}

fn finish_writers(writers: Vec<SpillWriter<Row, RowCodec>>) -> io::Result<()> {
    for writer in writers {
        writer.finish()?;
    }
    Ok(())
}

fn write_spilled_row(
    writer: &mut SpillWriter<Row, RowCodec>,
    row: &Row,
    build_side: bool,
    stats: &mut JoinStats,
) -> io::Result<()> {
    let bytes = writer.write(row)?;
    if build_side {
        stats.spilled_build_rows += 1;
        stats.spilled_build_bytes += bytes;
    } else {
        stats.spilled_probe_rows += 1;
        stats.spilled_probe_bytes += bytes;
    }
    Ok(())
}

/// Spill format: `[key: u64][payload length: u32][UTF-8 payload]`.
///
/// This is intentionally a logical format: it contains no pointers, bucket
/// capacity or allocator state from the in-memory hash table. The generic I/O
/// and file lifecycle live in `spill-io`; only this Join-specific format remains
/// in the operator crate.
#[derive(Clone, Copy, Debug)]
struct RowCodec;

impl SpillCodec<Row> for RowCodec {
    fn encode<W: Write>(&self, row: &Row, writer: &mut W) -> io::Result<()> {
        let key = row.key.ok_or_else(|| {
            invalid_input("NULL rows must not be written to inner-join spill files")
        })?;
        let payload = row.payload.as_bytes();
        let length = u32::try_from(payload.len())
            .map_err(|_| invalid_input("row payload is larger than u32::MAX"))?;
        writer.write_all(&key.to_le_bytes())?;
        writer.write_all(&length.to_le_bytes())?;
        writer.write_all(payload)
    }

    fn decode<R: Read>(&self, reader: &mut R) -> io::Result<Option<Row>> {
        let mut key_bytes = [0_u8; 8];
        if reader.read(&mut key_bytes[..1])? == 0 {
            return Ok(None);
        }
        reader.read_exact(&mut key_bytes[1..])?;
        let mut length_bytes = [0_u8; 4];
        reader.read_exact(&mut length_bytes)?;
        let length = u32::from_le_bytes(length_bytes) as usize;
        let mut payload = vec![0_u8; length];
        reader.read_exact(&mut payload)?;
        let payload = String::from_utf8(payload).map_err(|error| {
            io::Error::new(
                io::ErrorKind::InvalidData,
                format!("invalid UTF-8: {error}"),
            )
        })?;
        Ok(Some(Row::new(u64::from_le_bytes(key_bytes), payload)))
    }
}

fn invalid_input(message: &str) -> io::Error {
    io::Error::new(io::ErrorKind::InvalidInput, message)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sorted(mut rows: Vec<JoinedRow>) -> Vec<JoinedRow> {
        rows.sort();
        rows
    }

    #[test]
    fn in_memory_join_preserves_duplicates_and_sql_null_semantics() {
        let build = vec![Row::new(1, "b1"), Row::new(1, "b2"), Row::null("bn")];
        let probe = vec![Row::new(1, "p1"), Row::new(1, "p2"), Row::null("pn")];
        let config = JoinConfig {
            memory_budget_rows: 10,
            ..JoinConfig::default()
        };

        let result = hybrid_grace_hash_join(&build, &probe, &config).unwrap();

        assert_eq!(result.rows.len(), 4);
        assert_eq!(result.stats.null_build_rows, 1);
        assert_eq!(result.stats.null_probe_rows, 1);
        assert_eq!(result.events, vec![JoinEvent::InMemoryBuild { rows: 2 }]);
    }

    #[test]
    fn external_join_matches_the_in_memory_result() {
        let build: Vec<Row> = (0..64)
            .map(|key| Row::new(key, format!("build-{key}")))
            .chain([Row::new(7, "build-7-duplicate"), Row::null("ignored")])
            .collect();
        let probe: Vec<Row> = (0..72)
            .map(|key| Row::new(key, format!("probe-{key}")))
            .chain([Row::null("ignored")])
            .collect();

        let in_memory = hybrid_grace_hash_join(
            &build,
            &probe,
            &JoinConfig {
                memory_budget_rows: 128,
                ..JoinConfig::default()
            },
        )
        .unwrap();
        let external = hybrid_grace_hash_join(
            &build,
            &probe,
            &JoinConfig {
                memory_budget_rows: 5,
                partitions: 4,
                max_repartition_depth: 4,
            },
        )
        .unwrap();

        assert_eq!(sorted(external.rows), sorted(in_memory.rows));
        assert!(external.stats.spilled_build_rows > 0);
        assert!(external.stats.spilled_probe_rows > 0);
        assert!(external.stats.spilled_build_bytes > 0);
        assert!(external.stats.spilled_probe_bytes > 0);
        assert!(external.stats.restored_partitions > 0);
        assert!(external.stats.repartitions > 0);
    }

    #[test]
    fn retains_the_hybrid_partition_when_it_fits() {
        let config = JoinConfig {
            memory_budget_rows: 3,
            partitions: 4,
            max_repartition_depth: 4,
        };
        let keys_in_partition_zero: Vec<u64> = (0..100)
            .filter(|key| partition_for(*key, 0, config.partitions) == 0)
            .take(2)
            .collect();
        let mut build: Vec<Row> = keys_in_partition_zero
            .iter()
            .map(|key| Row::new(*key, format!("b-{key}")))
            .collect();
        build.extend(
            (100..140)
                .filter(|key| partition_for(*key, 0, config.partitions) != 0)
                .take(12)
                .map(|key| Row::new(key, format!("b-{key}"))),
        );
        let probe: Vec<Row> = build
            .iter()
            .map(|row| Row::new(row.key.unwrap(), format!("p-{}", row.key.unwrap())))
            .collect();

        let result = hybrid_grace_hash_join(&build, &probe, &config).unwrap();

        assert!(result.stats.hybrid_partition_kept);
        assert!(result.events.iter().any(|event| matches!(
            event,
            JoinEvent::ImmediateProbe { probe_rows, .. } if *probe_rows == keys_in_partition_zero.len()
        )));
    }

    #[test]
    fn reports_unsplittable_skew_at_the_depth_limit() {
        let build = vec![Row::new(42, "same-key"); 6];
        let probe = vec![Row::new(42, "probe")];
        let error = hybrid_grace_hash_join(
            &build,
            &probe,
            &JoinConfig {
                memory_budget_rows: 2,
                partitions: 2,
                max_repartition_depth: 2,
            },
        )
        .unwrap_err();

        assert_eq!(error.kind(), io::ErrorKind::OutOfMemory);
        assert!(error.to_string().contains("likely skew"));
    }
}
