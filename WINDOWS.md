# Native Windows Builds

The Windows entry point builds a selected, tested group of projects. It does not
attempt to build every experiment or initialize every research submodule.

## Prerequisites

- Windows 10/11 with x64 targets and PowerShell 5.1 or newer.
- Visual Studio 2022/2026 with **Desktop development with C++**, a Windows SDK,
  and the **C++ CMake tools for Windows** component.
- Git for downloading missing C++ dependencies.
- Rust with the `x86_64-pc-windows-msvc` toolchain for Rust projects.
- Python 3.8+ with `venv` and `pip` for ToyDB (verified locally with Python 3.12).

No administrator privileges or global PATH changes are needed. The script uses
`vswhere` to find Visual Studio, loads its MSVC environment, and locates bundled
CMake/Ninja when they are not on PATH. It restores the calling process's compiler
environment afterward.

## Commands

Run these from the repository root:

```powershell
# Build and test the supported C++ projects.
./tools/build-windows.ps1

# Build/test all projects listed in the support table.
./tools/build-windows.ps1 -Project all -Configuration Release

# Select one project.
./tools/build-windows.ps1 -Project query-engine
./tools/build-windows.ps1 -Project rlab -Configuration Release
./tools/build-windows.ps1 -Project rdb
./tools/build-windows.ps1 -Project toydb

# Include available C++ benchmarks in the build.
./tools/build-windows.ps1 -Project cpp -Configuration Release -Benchmarks

# Use a custom local output directory; paths with spaces are supported.
./tools/build-windows.ps1 -BuildRoot 'C:\dev\xlab builds'

# Build libraries only without test dependencies.
./tools/build-windows.ps1 -SkipTests -NoFetch

# Rebuild C++ outputs after changing compiler settings or recovering stale objects.
./tools/build-windows.ps1 -Clean
```

Outputs default to `%LOCALAPPDATA%\xlab-build`, outside the source checkout.
For C++ the default directory is `cpp\cpp-Ninja-native`; Rust executables are in
`rust\<project>\debug` or `release`. ToyDB has its own
`python\toydb-venv` environment and does not require activating it.

Rust's `RelWithDebInfo` selection currently uses the Cargo dev profile; only
`Release` selects Cargo's optimized release profile. Some existing Rust tests
are expensive in Debug, so Release is useful for a full workspace verification.

## Supported Projects

| Selector | Native Windows scope |
| --- | --- |
| `cpp` | The four C++ projects below, built together with shared dependencies. |
| `cclab` | Consistent hash library; enum, floating-point, copy-on-write column, and defer tests. |
| `kv-store` | TinyKV MemTable, SkipList, Arena, tests, and optional MemTable benchmark. |
| `query-engine` | Core library and hash-table/aggregation integration tests. |
| `thread-pool` | Global/work-stealing pool, deque tests, and optional latency/throughput benchmarks. |
| `rlab` | All six Rust workspace packages, including tests and doctests. |
| `rdb` | Database executable and storage tests using isolated OS temporary directories. |
| `toydb` | Editable Python package installation and existing pytest suite. |
| `all` | `cpp`, `rlab`, `rdb`, and `toydb`; failures are collected and reported. |

The query-engine checkout lacks its previously referenced `test_*.cc` and
`bench/bench_aggregation.cc` sources. CMake now discovers actual test files and
includes an integration suite; it reports the absent benchmark when requested.
This does not validate every prototype join/sort operation.

The full Linux `cclab` build is still available through its existing `build.sh`.
Native Windows defaults to `CCLAB_PORTABLE_ONLY=ON`. The root CMake build also
selects that subset on other operating systems. To select individual C++ modules
in a manual root build, use `XLAB_BUILD_CCLAB`, `XLAB_BUILD_KV_STORE`,
`XLAB_BUILD_QUERY_ENGINE`, and `XLAB_BUILD_THREAD_POOL`.

## Dependencies and Offline Builds

The CMake projects prefer existing `cc/thirdparty` sources or installed packages.
`XLAB_FETCH_DEPENDENCIES=ON` enables HTTPS downloads of missing dependencies.
The PowerShell entry point enables this by default, with these pinned revisions:

- GoogleTest v1.15.2: `b514bdc898e2951020cbdca1304b75f5950d1f59`.
- Google Benchmark v1.9.1: `96afad55c79e02f5dfca1374e772c2be72ba631b`.

`-NoFetch` disables first-time C++ dependency downloads. Existing fetched source
directories are reused without remote updates. For a fresh offline build,
initialize the required submodules beforehand or install their CMake packages.
This option does not disable Cargo or pip downloads; pre-populate their caches
separately when working offline.

Tests honor `BUILD_TESTING`; benchmarks honor `XLAB_BUILD_BENCHMARKS` and are off
by default. Compiler options are target-scoped, and threading uses
`Threads::Threads` instead of unconditional Unix library names.

## Working from WSL Shares

The current checkout is accessible through `\\wsl$\Ubuntu\home\lism\work\xlab`.
Windows compilation still uses Windows compilers and produces Windows `.exe`
files. The script translates the source path to the equivalent
`\\wsl.localhost\Ubuntu\...` share to avoid a literal `$` in generated Ninja rules.

Ninja also avoids Visual Studio/MSBuild's lowercasing of dependency paths on the
case-sensitive WSL filesystem and its structured-diagnostics URI failure for
`wsl$` paths. Build outputs and virtual environments stay on the Windows disk.
For native drive checkouts, an explicit `-Generator 'Visual Studio 17 2022'`
or `-Generator 'Visual Studio 18 2026'` is also available.

Chinese-only MSVC installations can emit a localized `/showIncludes` prefix
that CMake decodes incorrectly. The script supplies the matching prefix so
Ninja can track header dependencies and suppress the include trace correctly.

## Concurrency and Lifecycle Repairs

The original Rust MPMC/MPSC implementations freed nodes that were still referenced
by queue pointers. They now delegate reclamation to Crossbeam `SegQueue`; the
bounded variant uses `ArrayQueue`. Public push/pop APIs are retained. The MPSC
API now also safely permits multiple consumers. Historical algorithm examples
in the queue README describe the earlier educational implementation.

The C++ deque now uses a mutex-protected, growing ring buffer. It retains LIFO
local pops and FIFO steals, but is **not a lock-free Chase-Lev implementation**.
This protects `std::function` ownership, handles an empty pop, and prevents task
overwrites. Shutdown drains accepted tasks and concurrent `Stop()` calls wait
for worker termination. Victim lists are allocated once per worker.
The chained-submission benchmarks wait for completion outside the worker pool
to avoid exhausting workers with parents blocked on their children.

TinyKV initializes its Arena before constructing the SkipList. Its allocations
preserve natural alignment, reuse aligned free space, validate alignment and
size overflow, and transfer ownership during move assignment without explicitly
destroying a live object. Regression tests cover these paths in Release too.

## Other Modules

`io-uring`, `mini-seastar`, POSIX socket/web-server experiments, and the full
Linux system lab require Linux APIs and should run under WSL. LLVM/ANTLR,
Python native extensions, Tauri applications, Java/Go/Haskell projects, and
service-dependent applications need separate toolchains or dependencies and
are not part of this verified Windows group. Their existing build commands
have not been replaced.

Portable C++ builds, Rust workspace tests, RDB tests, and ToyDB tests are covered
by `.github/workflows/native-build.yml`. The workflow must run on GitHub to
establish CI results; local validation does not imply a completed remote run.

## Local Verification

Verified on 2026-10-07 using the current WSL-hosted checkout and Windows-native
MSVC 19.50, CMake 4.2.3, Rust 1.96, and Python 3.12:

| Check | Result |
| --- | --- |
| Windows C++ Debug | 50 CTest entries passed. |
| Windows C++ Release, including benchmark builds | 50 CTest entries passed. |
| Linux C++ Release under WSL, GCC 13.3 | 50 CTest entries passed. |
| Rust rlab workspace Release | 199 tests passed, including doctests. |
| RDB | 4 tests passed; native executable completed both sample SQL queries. |
| ToyDB | Package installed; 28 tests passed and 2 existing tests skipped. |
| Standalone cclab with Windows PowerShell 5.1 | 21 CTest entries passed. |
| Thread-pool chained-submission benchmarks | All four short runs completed without deadlock. |

Ninja's dependency database was also checked for TinyKV's Arena and MemTable
headers. Focused Rust formatting/Clippy checks completed; existing warnings in
the laboratory examples remain. The GitHub workflow has not been run remotely.
