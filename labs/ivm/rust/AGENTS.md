# Rust incremental aggregation lab

Read the repository root `AGENTS.md` and `RULES.md`; all identity, publication
and public-content safety requirements apply here without exceptions.

This is an independent, standard-library-only Cargo workspace. Do not add DBSP,
network, persistence or cross-topic dependencies to make a learning test pass.
Preserve the sibling Python prototypes unless a task explicitly changes them.

Required invariants:

- Materialized ZSet/Batch records are unique and have nonzero i64 weights.
  ZSet may have negative weights; TimeSeries cumulative bags may not.
- Check arithmetic; returning an error must leave input and tree state unchanged.
- Empty aggregation is None, not numeric zero. Test at least SUM/COUNT and MIN.
- Radix children carry cached aggregates; /0 and /64 must not shift by 64.
  Non-root internal nodes have two children; deletion compresses unary paths.
- Node deltas retract the entire old node and insert the entire new node.
  Replay must match snapshots with one node of weight 1 per live prefix.
- Cursor seeks never move backward. Include empty/exhausted/rewind tests.
- Compare incremental results with an independent full scan, not another use of
  the same tree algorithm. Separate correctness from performance claims.

From this directory, run:

```sh
cargo fmt -- --check
cargo clippy --offline --locked --all-targets -- -D warnings
cargo test --offline --locked
cargo test --offline --locked --release
cargo run --offline --locked --example time_series
```

Retain Cargo.lock compatibility with the declared minimum Rust toolchain.
Document actual local verification separately from configured remote CI.
