# Remaining book source retirement

76 source files from four roots were accepted into Cygnus via
[PR #7](https://github.com/LiShuMing/cygnus/pull/7). Accepted commit:
`ad36e55ea612f9a4a8fec3552f4a874610ab05f0`; exact tree:
`25d3103cf2d76dc4dfd31d1f6c48dab0aba1f872`.
[Post-merge CI](https://github.com/LiShuMing/cygnus/actions/runs/38689016663)
passed for that exact commit. Destination access requires existing repository
permission; this public retirement record does not change access or grant rights.

| Former source root | Files | Current home |
| --- | ---: | --- |
| `docs/books/calcite-code-book` | 22 | [Cygnus](https://github.com/LiShuMing/cygnus/tree/ad36e55ea612f9a4a8fec3552f4a874610ab05f0/books/calcite-code-book) |
| `docs/books/risingwave-book` | 12 | [Cygnus](https://github.com/LiShuMing/cygnus/tree/ad36e55ea612f9a4a8fec3552f4a874610ab05f0/books/risingwave-book) |
| `docs/books/claude-code-internals` | 21 | [Cygnus](https://github.com/LiShuMing/cygnus/tree/ad36e55ea612f9a4a8fec3552f4a874610ab05f0/books/claude-code-internals) |
| `docs/books/feiman-book` | 21 | [Cygnus](https://github.com/LiShuMing/cygnus/tree/ad36e55ea612f9a4a8fec3552f4a874610ab05f0/books/feiman-book) |

The [per-file ledger](2026-10-15-remaining-books-retirement.json) records only
source/destination paths, hashes, modes and acceptance references. It contains no
manuscript bodies or destination-private editorial metadata. Source and target
hashes may differ; the accepted migration records in Cygnus describe adaptation.
Acceptance establishes preservation and routing, not technical correctness,
completeness of the manuscripts or broader publication permission.

These four roots are removed completely without stubs. No other project source,
user runtime state, ignored files or repository history is purged. All other
cleanup changes belong to the same consolidated proposal; see
[cleanup boundaries](../meta/repository-cleanup.md).

## Recovery

Use ordinary `git revert` of the eventual cleanup commit to restore the tracked
source files. Exact pre-retirement sources also remain at xlab
`bf3e2ed45c12cc551fd44ef3cb89366970cd92ba` and the preserved backup
`fd15e65059ff7d0d01ed48b6347cd75881fb4b36`. Their Git blob and SHA-256 values
match the source ledger. Deleting current-tree copies is not secure erasure or
history rewriting.
