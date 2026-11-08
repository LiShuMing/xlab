# rlab - Rust Learning and Algorithms Library

This is a Rust workspace containing a library of algorithms/data structures and CLI tools.

## Workspace Structure


```
rlab/
├── Cargo.toml              # Workspace root
├── Cargo.lock              # Workspace lock file
├── lib/
│   └── rlab/               # Core library crate
│       ├── Cargo.toml
│       └── src/
│           ├── lib.rs      # Library root
│           └── common/
│               ├── mod.rs
│               └── sort/   # Sorting algorithms
│                   ├── mod.rs
│                   ├── benchmark.rs
│                   ├── simple.rs       # O(n²) sorts
│                   ├── efficient.rs    # O(n log n) sorts
│                   ├── integer.rs      # O(n) sorts
│                   └── quick_sort.rs
│               └── (more modules...)
│       └── tests/          # Integration tests
├── tools/
│   └── rlab-tools/         # CLI tools binary
│       ├── Cargo.toml
│       └── src/
│           ├── main.rs     # CLI entry point
│           └── addr2line.rs # DWARF address resolution
└── benches/                # Criterion benchmarks (placeholder)
```

## Crates

### `lib/rlab` - Core Library

The library crate provides:

- **Sorting Algorithms** (`rlab::sort`):
  - Simple: Bubble, Selection, Insertion, Shell, Gnome, Comb
  - Efficient: Quick, Merge, Heap, Tim, Intro
  - Integer: Counting, Radix (LSD/MSD), Bucket, Flash
  - Benchmarking utilities

- **Math Utilities** (`rlab`):
  - `add()` - Simple addition
  - `factorial()` - Factorial calculation
  - `gcd()` - Greatest common divisor

### `tools/rlab-tools` - CLI Tools

Command-line utilities:

1. **Sorting Benchmarks** (`--sort-bench`):
   ```bash
   rlab --sort-bench
   rlab --sort-bench --sizes 1000,10000 --algorithms quick,merge,heap
   ```

2. **Addr2line** - Address to source location:
   ```bash
   rlab /path/to/binary 0x401234
   ```

## Building

```bash
# Build entire workspace
cargo build

# Build in release mode
cargo build --release

# Build specific crate
cargo build -p rlab
cargo build -p rlab-tools
```

## Testing

```bash
# Run all tests
cargo test

# Run tests for specific crate
cargo test -p rlab
cargo test -p rlab-tools

# Run with output visible
cargo test -- --nocapture
```

## Running Tools

```bash
# Run sorting benchmarks
cargo run --release -- --sort-bench

# Run with custom options
cargo run --release -- --sort-bench \
  --sizes 1000,10000,100000 \
  --algorithms quick,merge,heap,radix-lsd \
  --distributions random,sorted,reverse

# Run addr2line
cargo run --release -- /usr/bin/ls 0x401000
```

## Adding New Code

### Adding a sorting algorithm

1. Add implementation to appropriate file:
   - `lib/rlab/src/common/sort/simple.rs` - O(n²) algorithms
   - `lib/rlab/src/common/sort/efficient.rs` - O(n log n) algorithms  
   - `lib/rlab/src/common/sort/integer.rs` - O(n) integer algorithms

2. Export in `lib/rlab/src/common/sort/mod.rs`:
   ```rust
   pub use your_file::your_sort;
   ```

3. Add to `SortAlgorithm` enum for benchmark support

4. Add unit tests in the same file

5. Add integration tests in `lib/rlab/tests/test_sort.rs`

### Adding a new tool

1. Add module to `tools/rlab-tools/src/`
2. Import and use in `tools/rlab-tools/src/main.rs`
3. Add CLI argument parsing

### Adding a new data structure

1. Create module in `lib/rlab/src/`
2. Export in `lib/rlab/src/lib.rs`
3. Add unit tests
4. Add integration tests in `lib/rlab/tests/`

## Dependencies

### Library (`lib/rlab`)
- `fastrand` - Fast random number generation

### Tools (`tools/rlab-tools`)
- `rlab` - The library crate
- `gimli` - DWARF parsing
- `object` - Object file parsing
- `memmap2` - Memory-mapped files
- `anyhow` - Error handling

## Algorithm Complexity Summary

| Algorithm | Time (avg) | Space | Stable | Category |
|-----------|------------|-------|--------|----------|
| Bubble | O(n²) | O(1) | Yes | Simple |
| Selection | O(n²) | O(1) | No | Simple |
| Insertion | O(n²) | O(1) | Yes | Simple |
| Shell | O(n^1.3) | O(1) | No | Simple |
| Quick | O(n log n) | O(log n) | No | Efficient |
| Merge | O(n log n) | O(n) | Yes | Efficient |
| Heap | O(n log n) | O(1) | No | Efficient |
| Tim | O(n log n) | O(n) | Yes | Hybrid |
| Intro | O(n log n) | O(log n) | No | Hybrid |
| Counting | O(n+k) | O(n+k) | Yes | Integer |
| Radix | O(d(n+b)) | O(n+b) | Yes | Integer |
| Bucket | O(n+k) | O(n+k) | Yes | Integer |

## 补充工程规范

以下条款原先独立成 `RULES.md`，已并入本文件。

### 公共 API 设计

- 公共条目在 crate 根重导出，调用方从 `rlab::` 可达；模块内按功能分组，`mod.rs` 只做聚合导出。
- 共享行为用 trait 表达（如 `Sorter`）；能用泛型的地方不写死具体类型。

### 错误处理

- 可失败操作返回 `Result<T, E>`，可空值用 `Option<T>`。
- 库用 `thiserror` 定义错误类型，应用层用 `anyhow`。
- 库代码禁止 `unwrap()`/`expect()`。

### 文档

- 所有 public 条目必须有 `///` 文档注释，模块级用 `//!`。
- 文档注释写复杂度、`# Panics`、`# Errors`、`# Safety`，并带可运行的 `# Examples`（doctest）。

### 测试分层

- 单元测试与被测代码同文件（`#[cfg(test)] mod tests`）。
- 集成测试放 `tests/`，基准放 `benches/`（Criterion），文档示例由 doctest 校验。
- 命令：`cargo test --workspace`、`cargo test -p rlab`、`cargo bench -p rlab`；优化前后用
  `--save-baseline` / `--baseline` 对比。

### unsafe 约定

尽量不用；每处 `unsafe` 块必须写 `// SAFETY:` 说明不变式与调用方义务，函数文档加 `# Safety`
段；unsafe 必须封装在安全抽象之后，并接受评审。

### 依赖策略

- 库 crate 尽量零外部依赖；工具 crate 可放宽。
- 已认可：`fastrand`（随机）、`thiserror`/`anyhow`（错误）、`nom`/`regex`（解析）、
  `tokio`（异步）、`clap`（CLI）、`serde`（序列化）、`criterion`（基准）。
- 新增依赖前先查工作区是否已有，再评估维护状态、体积与许可；共享依赖写进工作区
  `Cargo.toml` 并说明理由。

### CI 必过检查

`cargo fmt --all -- --check`、`cargo clippy --all-targets --all-features -- -D warnings`、
`cargo test --workspace`、`cargo doc --no-deps`。

### 提交信息

`<type>(<scope>): <description>`，type 取 `feat`/`fix`/`docs`/`style`/`refactor`/`perf`/`test`/`chore`，
例如 `perf(radix): optimize counting phase`。

### 代码审查清单

- [ ] 命名符合约定
- [ ] public 条目都有文档
- [ ] 新功能带测试
- [ ] `cargo clippy` 无告警
- [ ] 已跑 `cargo fmt`
- [ ] 库代码无 `unwrap()`/`expect()`
- [ ] unsafe 有安全说明
- [ ] 性能关键路径有基准
- [ ] 面向用户的改动更新了 `CHANGELOG.md`

### 可选改进方向（原 TODOS.md 的 NOTES）

- 排序：并行版本（并行归并）、整数排序的 SIMD 变体、更好的枢轴 introsort。
- 数据结构：更多无锁结构（栈、链表）、B 树类索引、arena 分配器改善缓存局部性。
- 测试与文档：`proptest` 属性测试、复杂结构 fuzz、内存占用基准、book 式文档、
  全算法复杂度表。

