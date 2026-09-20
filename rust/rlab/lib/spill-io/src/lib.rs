//! Reusable spill-file I/O primitives for external-memory algorithms.
//!
//! This crate owns only the physical spill concerns:
//!
//! - temporary directory and file lifetime;
//! - buffered sequential reads and writes;
//! - operator-provided record codecs;
//! - record and byte counters.
//!
//! Join, aggregate and sort algorithms keep ownership of partitioning, run
//! generation, merge policy and record formats.

use std::fs::{self, File, OpenOptions};
use std::io::{self, BufReader, BufWriter, Read, Write};
use std::marker::PhantomData;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

static NEXT_DIRECTORY_ID: AtomicU64 = AtomicU64::new(0);

/// Encodes and decodes one logical record in an operator-specific spill format.
///
/// A codec must return `Ok(None)` only when it observes a clean end-of-file before
/// reading any byte of the next record. Truncated records should return an error.
pub trait SpillCodec<T> {
    fn encode<W: Write>(&self, value: &T, writer: &mut W) -> io::Result<()>;

    fn decode<R: Read>(&self, reader: &mut R) -> io::Result<Option<T>>;
}

/// A file managed by a [`SpillDirectory`].
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SpillFile {
    path: PathBuf,
}

impl SpillFile {
    pub fn path(&self) -> &Path {
        &self.path
    }

    pub fn len(&self) -> io::Result<u64> {
        Ok(fs::metadata(&self.path)?.len())
    }

    pub fn is_empty(&self) -> io::Result<bool> {
        Ok(self.len()? == 0)
    }
}

/// Owns a unique temporary directory and removes it recursively on drop.
#[derive(Debug)]
pub struct SpillDirectory {
    root: PathBuf,
    next_file_id: u64,
}

impl SpillDirectory {
    /// Creates a spill directory below the process temporary directory.
    pub fn new(prefix: &str) -> io::Result<Self> {
        Self::new_in(std::env::temp_dir(), prefix)
    }

    /// Creates a spill directory below `parent`.
    pub fn new_in(parent: impl AsRef<Path>, prefix: &str) -> io::Result<Self> {
        validate_label(prefix)?;
        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_err(|error| io::Error::other(format!("clock error: {error}")))?
            .as_nanos();

        for _ in 0..100 {
            let id = NEXT_DIRECTORY_ID.fetch_add(1, Ordering::Relaxed);
            let root = parent
                .as_ref()
                .join(format!("{prefix}-{}-{timestamp}-{id}", std::process::id()));
            match fs::create_dir(&root) {
                Ok(()) => {
                    return Ok(Self {
                        root,
                        next_file_id: 0,
                    });
                }
                Err(error) if error.kind() == io::ErrorKind::AlreadyExists => continue,
                Err(error) => return Err(error),
            }
        }

        Err(io::Error::new(
            io::ErrorKind::AlreadyExists,
            "could not allocate a unique spill directory",
        ))
    }

    pub fn path(&self) -> &Path {
        &self.root
    }

    /// Reserves an empty spill file with a readable label and a unique numeric ID.
    pub fn create_file(&mut self, label: &str) -> io::Result<SpillFile> {
        validate_label(label)?;
        let id = self.next_file_id;
        self.next_file_id += 1;
        let path = self.root.join(format!("{id:06}-{label}.spill"));
        OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&path)?;
        Ok(SpillFile { path })
    }
}

impl Drop for SpillDirectory {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.root);
    }
}

/// Final counters returned after closing a writer.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct SpillWriteStats {
    pub records: usize,
    pub bytes: u64,
}

/// Buffered typed writer for one spill file.
#[derive(Debug)]
pub struct SpillWriter<T, C> {
    writer: CountingWriter<BufWriter<File>>,
    codec: C,
    records: usize,
    _record: PhantomData<fn(&T)>,
}

impl<T, C: SpillCodec<T>> SpillWriter<T, C> {
    pub fn create(file: &SpillFile, codec: C) -> io::Result<Self> {
        let file = OpenOptions::new()
            .write(true)
            .truncate(true)
            .open(file.path())?;
        Ok(Self {
            writer: CountingWriter::new(BufWriter::new(file)),
            codec,
            records: 0,
            _record: PhantomData,
        })
    }

    /// Writes one logical record and returns its encoded byte size.
    pub fn write(&mut self, value: &T) -> io::Result<u64> {
        let before = self.writer.bytes;
        self.codec.encode(value, &mut self.writer)?;
        self.records += 1;
        Ok(self.writer.bytes - before)
    }

    pub fn stats(&self) -> SpillWriteStats {
        SpillWriteStats {
            records: self.records,
            bytes: self.writer.bytes,
        }
    }

    /// Flushes buffered data and closes the writer.
    pub fn finish(mut self) -> io::Result<SpillWriteStats> {
        self.writer.flush()?;
        Ok(self.stats())
    }
}

/// Counters exposed while or after reading a spill file.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct SpillReadStats {
    pub records: usize,
    pub bytes: u64,
}

/// Buffered typed reader for one spill file.
#[derive(Debug)]
pub struct SpillReader<T, C> {
    reader: CountingReader<BufReader<File>>,
    codec: C,
    records: usize,
    finished: bool,
    _record: PhantomData<fn() -> T>,
}

impl<T, C: SpillCodec<T>> SpillReader<T, C> {
    pub fn open(file: &SpillFile, codec: C) -> io::Result<Self> {
        Ok(Self {
            reader: CountingReader::new(BufReader::new(File::open(file.path())?)),
            codec,
            records: 0,
            finished: false,
            _record: PhantomData,
        })
    }

    pub fn read_next(&mut self) -> io::Result<Option<T>> {
        if self.finished {
            return Ok(None);
        }
        match self.codec.decode(&mut self.reader)? {
            Some(value) => {
                self.records += 1;
                Ok(Some(value))
            }
            None => {
                self.finished = true;
                Ok(None)
            }
        }
    }

    pub fn stats(&self) -> SpillReadStats {
        SpillReadStats {
            records: self.records,
            bytes: self.reader.bytes,
        }
    }
}

#[derive(Debug)]
struct CountingWriter<W> {
    inner: W,
    bytes: u64,
}

impl<W> CountingWriter<W> {
    fn new(inner: W) -> Self {
        Self { inner, bytes: 0 }
    }
}

impl<W: Write> Write for CountingWriter<W> {
    fn write(&mut self, buffer: &[u8]) -> io::Result<usize> {
        let written = self.inner.write(buffer)?;
        self.bytes += written as u64;
        Ok(written)
    }

    fn flush(&mut self) -> io::Result<()> {
        self.inner.flush()
    }
}

#[derive(Debug)]
struct CountingReader<R> {
    inner: R,
    bytes: u64,
}

impl<R> CountingReader<R> {
    fn new(inner: R) -> Self {
        Self { inner, bytes: 0 }
    }
}

impl<R: Read> Read for CountingReader<R> {
    fn read(&mut self, buffer: &mut [u8]) -> io::Result<usize> {
        let read = self.inner.read(buffer)?;
        self.bytes += read as u64;
        Ok(read)
    }
}

fn validate_label(label: &str) -> io::Result<()> {
    if label.is_empty()
        || !label
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_' | b'.'))
    {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "spill labels must contain only ASCII letters, digits, '-', '_' or '.'",
        ));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[derive(Clone, Copy, Debug)]
    struct U64Codec;

    impl SpillCodec<u64> for U64Codec {
        fn encode<W: Write>(&self, value: &u64, writer: &mut W) -> io::Result<()> {
            writer.write_all(&value.to_le_bytes())
        }

        fn decode<R: Read>(&self, reader: &mut R) -> io::Result<Option<u64>> {
            let mut bytes = [0_u8; 8];
            if reader.read(&mut bytes[..1])? == 0 {
                return Ok(None);
            }
            reader.read_exact(&mut bytes[1..])?;
            Ok(Some(u64::from_le_bytes(bytes)))
        }
    }

    #[test]
    fn typed_records_round_trip_with_stats() {
        let mut directory = SpillDirectory::new("spill-io-test").unwrap();
        let file = directory.create_file("partition-0").unwrap();
        let mut writer = SpillWriter::create(&file, U64Codec).unwrap();
        for value in [10, 20, 30] {
            assert_eq!(writer.write(&value).unwrap(), 8);
        }
        assert_eq!(
            writer.finish().unwrap(),
            SpillWriteStats {
                records: 3,
                bytes: 24,
            }
        );
        assert_eq!(file.len().unwrap(), 24);

        let mut reader = SpillReader::open(&file, U64Codec).unwrap();
        assert_eq!(reader.read_next().unwrap(), Some(10));
        assert_eq!(reader.read_next().unwrap(), Some(20));
        assert_eq!(reader.read_next().unwrap(), Some(30));
        assert_eq!(reader.read_next().unwrap(), None);
        assert_eq!(
            reader.stats(),
            SpillReadStats {
                records: 3,
                bytes: 24,
            }
        );
    }

    #[test]
    fn directory_drop_removes_all_spill_files() {
        let path = {
            let mut directory = SpillDirectory::new("spill-cleanup-test").unwrap();
            let path = directory.path().to_path_buf();
            directory.create_file("run-0").unwrap();
            assert!(path.exists());
            path
        };
        assert!(!path.exists());
    }

    #[test]
    fn rejects_path_traversal_in_labels() {
        let mut directory = SpillDirectory::new("spill-label-test").unwrap();
        let error = directory.create_file("../outside").unwrap_err();
        assert_eq!(error.kind(), io::ErrorKind::InvalidInput);
    }

    #[test]
    fn truncated_record_is_not_treated_as_clean_eof() {
        let mut directory = SpillDirectory::new("spill-truncated-test").unwrap();
        let file = directory.create_file("broken").unwrap();
        fs::write(file.path(), [1_u8, 2, 3]).unwrap();
        let mut reader = SpillReader::open(&file, U64Codec).unwrap();
        let error = reader.read_next().unwrap_err();
        assert_eq!(error.kind(), io::ErrorKind::UnexpectedEof);
    }
}
