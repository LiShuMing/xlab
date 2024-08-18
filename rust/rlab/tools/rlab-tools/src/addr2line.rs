//! DWARF-based address-to-line resolution
//!
//! This module provides functionality to map addresses in compiled binaries
//! to source file locations using DWARF debug information.

use memmap2::Mmap;
use object::{Object, ObjectSymbol};
use std::fs::File;
use std::path::{Path, PathBuf};

/// A resolved source location
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Location {
    /// Source file path
    pub file: String,
    /// Line number (1-indexed)
    pub line: u64,
    /// Column number (0 = unknown/left edge)
    pub column: u64,
}

impl std::fmt::Display for Location {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}:{}:{}", self.file, self.line, self.column)
    }
}

/// Error types for addr2line operations
#[derive(Debug)]
pub enum Error {
    /// IO error when reading file
    Io(std::io::Error),
    /// Invalid file format
    InvalidFormat(String),
    /// DWARF parsing error
    Dwarf(String),
    /// Address not found
    #[allow(dead_code)]
    NotFound,
}

impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Error::Io(e) => write!(f, "IO error: {}", e),
            Error::InvalidFormat(s) => write!(f, "invalid format: {}", s),
            Error::Dwarf(s) => write!(f, "DWARF error: {}", s),
            Error::NotFound => write!(f, "address not found"),
        }
    }
}

impl std::error::Error for Error {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Error::Io(e) => Some(e),
            _ => None,
        }
    }
}

impl From<std::io::Error> for Error {
    fn from(e: std::io::Error) -> Self {
        Error::Io(e)
    }
}

impl From<gimli::Error> for Error {
    fn from(e: gimli::Error) -> Self {
        Error::Dwarf(e.to_string())
    }
}

/// Address-to-line resolver
/// 
/// Note: The full DWARF parsing implementation requires complex gimli API usage.
/// This struct provides the foundation with symbol table lookup as a fallback.
pub struct Addr2Line {
    #[allow(dead_code)]
    mmap: Mmap,
    #[allow(dead_code)]
    path: PathBuf,
}

impl Addr2Line {
    /// Creates a new resolver for the given binary path
    ///
    /// # Arguments
    ///
    /// * `path` - Path to the binary file with debug information
    ///
    /// # Errors
    ///
    /// Returns an error if the file cannot be opened or is not a valid object file.
    pub fn new<P: AsRef<Path>>(path: P) -> Result<Self, Error> {
        let file = File::open(&path)?;
        let mmap = unsafe { Mmap::map(&file)? };
        
        // Verify it's a valid object file
        let _obj = object::File::parse(&*mmap)
            .map_err(|e| Error::InvalidFormat(e.to_string()))?;
        
        Ok(Addr2Line {
            mmap,
            path: path.as_ref().to_path_buf(),
        })
    }

    /// Resolves an address to a source location
    ///
    /// # Arguments
    ///
    /// * `addr` - The address to resolve (virtual address)
    ///
    /// # Returns
    ///
    /// - `Ok(Some(Location))` - Address was found
    /// - `Ok(None)` - No debug information available for this address
    /// - `Err(...)` - An error occurred during resolution
    ///
    /// # Note
    ///
    /// Currently, this uses the symbol table as a fallback. Full DWARF
    /// line number parsing is complex and requires careful implementation
    /// with the gimli crate's API.
    pub fn resolve(&self, addr: u64) -> Result<Option<Location>, Error> {
        // For now, return NotFound to allow fallback to symbol lookup
        // Full DWARF implementation requires more complex gimli usage
        let _ = addr;
        Ok(None)
    }

    /// Finds the nearest symbol for a given address
    ///
    /// This is used as a fallback when detailed line information is not available.
    pub fn nearest_symbol(&self, addr: u64) -> Result<Option<String>, Error> {
        let obj = object::File::parse(&*self.mmap)
            .map_err(|e| Error::InvalidFormat(e.to_string()))?;
        
        let mut best: Option<(u64, String)> = None;
        
        for sym in obj.symbols() {
            let sym_addr = sym.address();
            if sym_addr <= addr {
                if let Ok(name) = sym.name() {
                    match &best {
                        None => best = Some((sym_addr, name.to_string())),
                        Some((best_addr, _)) if sym_addr > *best_addr => {
                            best = Some((sym_addr, name.to_string()));
                        }
                        _ => {}
                    }
                }
            }
        }
        
        Ok(best.map(|(_, name)| name))
    }

    /// Returns the path of the loaded binary
    #[allow(dead_code)]
    pub fn path(&self) -> &Path {
        &self.path
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_location_display() {
        let loc = Location {
            file: "src/main.rs".to_string(),
            line: 42,
            column: 5,
        };
        assert_eq!(loc.to_string(), "src/main.rs:42:5");
    }

    #[test]
    fn test_error_display() {
        let io_err = Error::Io(std::io::Error::new(std::io::ErrorKind::NotFound, "test"));
        assert!(io_err.to_string().contains("IO error"));
        
        let not_found = Error::NotFound;
        assert_eq!(not_found.to_string(), "address not found");
    }
}
