mod common;

use gimli::{read, EndianSlice, LittleEndian, RunTimeEndian};
use memmap2::Mmap;
use object::{Object, ObjectSection};
use std::borrow::Cow;
use std::{env, fs::File, path::Path};

const THRESHOLD: i32 = 100;

fn is_big(n: i32) -> bool {
    return n > THRESHOLD;
}

fn apply<F>(f: F)
where
    F: FnOnce(),
{
    f();
}

fn abs_all(input: &mut Cow<'_, [i32]>) {
    for i in 0..input.len() {
        let v = input[i];
        if v < 0 {
            // Clones into a vector if not already owned.
            input.to_mut()[i] = -v;
        }
    }
}

fn test1() {
    // Accessing the constant
    let n = 1000;
    println!("{} is {}", n, if is_big(n) { "big" } else { "small" });

    // closure
    let add_one = |x: i32| -> i32 { x + 1 + n };

    // Call the closure with type anonymity
    apply(|| println!("Hello, world!"));

    println!("add_one(1):{}", add_one(1));
    // Call a function from the library
    println!("Going to call libary function");

    // No clone occurs because `input` doesn't need to be mutated.
    let slice = [0, 1, 2];
    let mut input = Cow::from(&slice[..]);
    abs_all(&mut input);

    // Clone occurs because `input` needs to be mutated.
    let slice = [-1, 0, 1];
    let mut input = Cow::from(&slice[..]);
    abs_all(&mut input);

    // No clone occurs because `input` is already owned.
    let mut input = Cow::from(vec![-1, 0, 1]);
    abs_all(&mut input);
}

/// Minimal addr->file:line using DWARF .debug_line
///
/// Usage:
///   mini_addr2line <path-to-elf> <hex-address>
/// Example:
///   mini_addr2line ./a.out 0x401234
fn main() -> anyhow::Result<()> {
    let args: Vec<String> = env::args().collect();
    if args.len() != 3 {
        eprintln!("usage: {} <elf> <addr-hex>", args[0]);
        std::process::exit(2);
    }
    let elf_path = &args[1];
    let query_addr = parse_addr(&args[2])?;

    let (file, mmap) = open_object(elf_path)?;
    let endian = match file.is_little_endian() {
        true => RunTimeEndian::Little,
        false => RunTimeEndian::Big,
    };

    // Load DWARF sections into gimli::Dwarf
    let dwarf = load_dwarf(&file, &mmap, endian)?;

    // Iterate all compile units (CU) and try to locate a match in .debug_line
    let mut found = false;
    let mut units = dwarf.units();
    while let Some(header) = units.next()? {
        let unit = dwarf.unit(header)?;
        if let Some(program) = unit.line_program.clone() {
            if let Some((file_name, line, column)) =
                lookup_in_line_program(&dwarf, &unit, &program, query_addr)?
            {
                println!("{}:{}:{}", file_name, line, column.unwrap_or(0));
                found = true;
                break;
            }
        }
    }

    if !found {
        // Fallback: try to print nearest symbol (no line info)
        if let Some(name) = nearest_symbol(&file, query_addr) {
            println!("{}:+0x0 (no line info)", name);
        } else {
            println!("??:0:0");
        }
    }

    Ok(())
}

/// Parse hex string like "0x401234" or "401234"
fn parse_addr(s: &str) -> anyhow::Result<u64> {
    let t = s.trim_start_matches("0x");
    let v = u64::from_str_radix(t, 16)?;
    Ok(v)
}

/// Open ELF and memory-map file
fn open_object(path: &str) -> anyhow::Result<(object::File<'static>, Mmap)> {
    let file = File::open(Path::new(path))?;
    let mmap = unsafe { Mmap::map(&file)? };
    // SAFETY: We hold mmap alive for the lifetime of returned object::File
    let obj = object::File::parse(&*mmap)?;
    Ok((
        unsafe { std::mem::transmute::<_, object::File<'static>>(obj) },
        mmap,
    ))
}

/// Load all DWARF sections that we need
fn load_dwarf<'a>(
    obj: &object::File<'a>,
    _mmap: &'a Mmap,
    endian: RunTimeEndian,
) -> anyhow::Result<read::Dwarf<EndianSlice<'a, RunTimeEndian>>> {
    // Helper to read a named section; returns empty slice if absent.
    let load_section = |name: &str| -> EndianSlice<'a, RunTimeEndian> {
        if let Some(sec) = obj.section_by_name(name) {
            let bytes = sec.uncompressed_data().unwrap_or(Cow::Borrowed(&[]));
            EndianSlice::new(&bytes, endian)
        } else {
            EndianSlice::new(&[], endian)
        }
    };
    use std::borrow::Cow;

    let dwarf = read::Dwarf {
        debug_abbrev: read::DebugAbbrev::new(load_section(".debug_abbrev").slice(), endian),
        debug_addr: read::DebugAddr::new(load_section(".debug_addr").slice(), endian),
        debug_info: read::DebugInfo::new(load_section(".debug_info").slice(), endian),
        debug_line: read::DebugLine::new(load_section(".debug_line").slice(), endian),
        debug_line_str: read::DebugLineStr::new(load_section(".debug_line_str").slice(), endian),
        debug_str: read::DebugStr::new(load_section(".debug_str").slice(), endian),
        debug_str_offsets: read::DebugStrOffsets::new(
            load_section(".debug_str_offsets").slice(),
            endian,
        ),
        debug_ranges: read::DebugRanges::new(load_section(".debug_ranges").slice(), endian),
        debug_rnglists: read::DebugRngLists::new(load_section(".debug_rnglists").slice(), endian),
        debug_aranges: read::DebugAranges::new(load_section(".debug_aranges").slice(), endian),
        debug_types: read::DebugTypes::new(load_section(".debug_types").slice(), endian),
        debug_pubnames: read::DebugPubNames::new(load_section(".debug_pubnames").slice(), endian),
        debug_pubtypes: read::DebugPubTypes::new(load_section(".debug_pubtypes").slice(), endian),
        locations: read::LocationLists::new(load_section(".debug_loc").slice(), endian),
        debug_loclists: read::DebugLocLists::new(load_section(".debug_loclists").slice(), endian),
        debug_frame: read::DebugFrame::new(load_section(".debug_frame").slice(), endian),
        eh_frame: read::EhFrame::new(load_section(".eh_frame").slice(), endian),
        debug_sup: read::DebugSup::new(load_section(".debug_sup").slice(), endian),
        debug_names: read::DebugNames::new(load_section(".debug_names").slice(), endian),
        debug_cu_index: read::DebugCuIndex::from(load_section(".debug_cu_index").slice(), endian),
        debug_tu_index: read::DebugTuIndex::from(load_section(".debug_tu_index").slice(), endian),
    };
    Ok(dwarf)
}

/// Walk a CU's line program and do a predecessor search:
/// find the last row with addr <= query and next row addr > query.
fn lookup_in_line_program<R>(
    dwarf: &read::Dwarf<R>,
    unit: &read::Unit<R>,
    program: &read::LineProgram<R>,
    query_addr: u64,
) -> anyhow::Result<Option<(String, u64, Option<u64>)>>
where
    R: read::Reader<Offset = usize>,
{
    let header = program.header();
    let mut rows = header.rows();
    let mut prev_row: Option<read::LineRow> = None;

    while let Some((_, row)) = rows.next_row()? {
        // Each 'row' is a snapshot of the DWARF line machine.
        // end_sequence means "gap"; reset predecessor chain.
        if row.end_sequence() {
            prev_row = None;
            continue;
        }

        let addr = row.address();
        match prev_row {
            None => {
                // We don't know the start bound yet; move on.
                prev_row = Some(row.clone());
            }
            Some(ref last) => {
                let last_addr = last.address();
                if last_addr <= query_addr && query_addr < addr {
                    // Hit! Use 'last' as the mapping row.
                    return Ok(resolve_row_path(dwarf, unit, last));
                }
                prev_row = Some(row.clone());
            }
        }
    }

    // If query falls after the last row of a sequence, the last row applies.
    if let Some(last) = prev_row {
        if last.address() <= query_addr {
            return Ok(resolve_row_path(dwarf, unit, &last));
        }
    }
    Ok(None)
}

/// Convert a LineRow to (file path, line, column)
fn resolve_row_path<R>(
    dwarf: &read::Dwarf<R>,
    unit: &read::Unit<R>,
    row: &read::LineRow,
) -> anyhow::Result<Option<(String, u64, Option<u64>)>>
where
    R: read::Reader<Offset = usize>,
{
    let (file_path, _dir_opt) = file_name_of_row(dwarf, unit, row)?;
    let line = row.line().map(|l| l.get()).unwrap_or(0);
    let col = row.column().map(|c| match c {
        gimli::ColumnType::LeftEdge => 0,
        gimli::ColumnType::Column(val) => val.get(),
    });
    Ok(Some((file_path, line, col)))
}

/// Get resolved file name for a row (handles file table + directory).
fn file_name_of_row<R>(
    dwarf: &read::Dwarf<R>,
    unit: &read::Unit<R>,
    row: &read::LineRow,
) -> anyhow::Result<(String, Option<String>)>
where
    R: read::Reader<Offset = usize>,
{
    let header = unit
        .line_program
        .as_ref()
        .expect("line program is present")
        .header();

    let file_entry = row
        .file(header)
        .ok_or_else(|| anyhow::anyhow!("missing file entry"))?;

    // Resolve directory
    let dir = file_entry
        .directory(header)
        .and_then(|d| d.to_string_lossy().ok())
        .map(|s| s.into_owned());

    let file_name = file_entry
        .path_name()
        .to_string_lossy()
        .map(|s| s.into_owned())
        .unwrap_or_else(|_| "<bad-utf8>".to_string());

    // Combine dir/file if dir exists
    let path = if let Some(ref d) = dir {
        format!("{}/{}", d, file_name)
    } else {
        file_name
    };

    Ok((path, dir))
}

/// Very small fallback: nearest symbol by address.
fn nearest_symbol(obj: &object::File<'_>, addr: u64) -> Option<String> {
    let mut best: Option<(u64, &str)> = None;
    for sym in obj.symbols() {
        if sym.address() <= addr {
            if let Ok(name) = sym.name() {
                match best {
                    None => best = Some((sym.address(), name)),
                    Some((best_addr, _)) if sym.address() > best_addr => {
                        best = Some((sym.address(), name))
                    }
                    _ => {}
                }
            }
        }
    }
    best.map(|(_, n)| n.to_string())
}
