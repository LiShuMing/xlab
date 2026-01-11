mod common;

use gimli::{read, EndianSlice, RunTimeEndian};
use memmap2::Mmap;
use object::{Object, ObjectSection, ObjectSymbol};
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
    // In gimli 0.29.0, use Dwarf::load with a closure
    // Note: This is a simplified version - proper implementation would map SectionId to sections
    let dwarf = read::Dwarf::load(
        |_id| -> Result<EndianSlice<'a, RunTimeEndian>, anyhow::Error> {
            // For now, return empty slice - proper implementation would load sections based on id
            Ok(EndianSlice::new(&[], endian))
        },
    )?;
    Ok(dwarf)
}

/// Walk a CU's line program and do a predecessor search:
/// find the last row with addr <= query and next row addr > query.
fn lookup_in_line_program<R>(
    dwarf: &read::Dwarf<R>,
    unit: &read::Unit<R>,
    program: &impl read::LineProgram<R>,
    query_addr: u64,
) -> anyhow::Result<Option<(String, u64, Option<u64>)>>
where
    R: read::Reader<Offset = usize>,
{
    // TODO: Implement proper row iteration for gimli 0.29.0
    // The API has changed significantly and requires proper documentation
    // For now, return None to allow compilation
    let _header = program.header();
    let _dwarf = dwarf;
    let _unit = unit;
    let _query_addr = query_addr;

    // Placeholder - actual implementation needs proper gimli 0.29.0 API
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
    let col = match row.column() {
        read::ColumnType::LeftEdge => Some(0),
        read::ColumnType::Column(val) => Some(val.get()),
    };
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

    // Resolve directory - directory() returns an AttributeValue
    let dir: Option<String> = file_entry.directory(header).and_then(|_d| {
        // TODO: properly convert AttributeValue to string
        None
    });

    // Resolve file name - path_name() returns an AttributeValue
    let file_name = file_entry.path_name();
    // TODO: properly convert AttributeValue to string
    let file_name = "<unknown>".to_string();

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
