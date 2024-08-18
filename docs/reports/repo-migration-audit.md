# xlab Migration Audit

Date: 2026-05-10

This audit records the current repository reorganization boundary. It is meant to
make the large delete/add state reviewable before committing or pruning code.

## Current Git Shape

At the time of this audit:

| Kind | Count | Notes |
| --- | ---: | --- |
| Deleted tracked paths | 381 | Mostly old Java, Rust, C++ lab, and Python toy paths. |
| New/untracked paths | 3000+ | Mostly reorganized project trees and documentation. |
| Staged cleanup/docs paths | 10 | Root docs, `.gitignore`, `.gitmodules`, `rust/optd` cleanup. |

The repository size is healthy after cleanup: about `211M` total, with `.git`
about `153M` and the working tree about `58M`.

## Deleted Path Clusters

| Old path | Deleted count | Current path exists? | Audit status | Notes |
| --- | ---: | --- | --- | --- |
| `cc/cclab/bench` | 29 | No | Needs review | Old benchmark tree removed from `cc/cclab`; confirm whether covered by `cc/ccbench` or intentionally dropped. |
| `cc/cclab/main` | 9 | No | Likely moved | New `cc/cclab/src` exists and appears to replace the old `main` layout. |
| `cc/cclab/test/*.cpp` | 8 | Partially | Likely moved | New `cc/cclab/test/{common,utils,interview,tools}` exists with `.cc` tests. |
| `cc/interpreter` | 15 | No | Likely moved | New `cc/projects/interpreter` exists. Confirm all yacc/lex/common files migrated. |
| `cc/sr` | 6 | No | Needs review | Possible deprecated StarRocks scratch area. Confirm no active build dependency. |
| `go/hello/hello` | 1 | No | Cleanup candidate | Compiled binary; deletion is expected. |
| `java/dropwizard` | 16 | No | Needs review | Old standalone sample removed; confirm no replacement needed. |
| `java/groovy` | 4 | No | Likely moved | Probably folded into `java/xlab-itest/xlab-groovy`. |
| `java/jlab` | 8 | No | Likely moved | Probably folded into `java/xlab-itest/xlab-jlib` or interview modules. |
| `java/kotlin` | 7 | No | Needs review | No obvious new Kotlin module seen; confirm deprecated or relocate. |
| `java/leetcode` | 113 | No | Needs review | Large algorithm set removed; confirm whether superseded by `cc/algo` or should remain under Java. |
| `java/scala` | 23 | No | Likely moved | Probably folded into `java/xlab-itest/xlab-spark` / Scala experiments. |
| `java/spark-tools` | 4 | No | Likely moved | New `java/xlab-itest/xlab-spark` exists. |
| `java/spring` | 25 | No | Likely moved | New `java/xlab-itest/xlab-spring` exists. |
| `java/thread` | 64 | No | Needs review | Old concurrency examples removed; confirm whether folded into `java/xlab-itest/xlab-interview`. |
| `python/sqlparser` | 1 | No | Needs review | Confirm whether superseded by parser work under `python/projects`. |
| `python/sr.py` | 1 | No | Needs review | Single script removed; confirm whether obsolete. |
| `python/toy` | 7 | No | Likely moved | Probably superseded by `python/projects/py-toydb` or `python/pylab`. |
| `rust/arithmetic-expression-evaluator` | 8 | No | Needs review | Confirm deprecated or move under `rust/projects`. |
| `rust/concurrent-map` | 16 | No | Needs review | Third-party-like code removed; confirm it should be submodule/reference instead. |
| `rust/first-program` | 3 | No | Cleanup candidate | Intro experiment; likely safe to drop after confirmation. |
| `rust/my-first-lib` | 4 | No | Cleanup candidate | Intro experiment; likely safe to drop after confirmation. |
| `rust/optd` | 1 | No | Cleanup candidate | Old gitlink removed; `.gitmodules` now points to `rust/thirdparty/optd`. |
| `rust/toy` | 8 | No | Likely moved | Likely superseded by `rust/rlab` or `rust/projects`. |

## New Path Clusters To Review

These are the largest new path families that should be reviewed as coherent
units before staging:

| New path family | Purpose inferred | Review focus |
| --- | --- | --- |
| `cc/algo` | C++ algorithm lab replacing scattered algorithm examples. | Build entry, README accuracy, whether Java LeetCode was intentionally dropped. |
| `cc/cclab/src` and `cc/cclab/test/*` | Reworked C++ core lab layout. | Confirm old `main` and tests are fully represented. |
| `cc/projects/*` | Split C++ experiments into standalone project folders. | Confirm old `cc/interpreter` migration and per-project build docs. |
| `cc/ccbench`, `cc/srlab`, `cc/simd`, `cc/tools` | Specialized C++ labs/tools. | Decide whether old `cc/cclab/bench` should map here. |
| `java/xlab-itest/*` | Consolidated Java/Groovy/Scala/Spring/Spark/interview labs. | Map old Java modules to new modules explicitly. |
| `java/xlab-iceberg` | Iceberg-specific Java project. | Ensure independent build docs. |
| `python/projects/*` | Consolidated Python app/research projects. | Identify generated data vs source; keep `.env.example` only. |
| `python/pylab` | Core Python lab. | Confirm old `python/toy` and `python/sqlparser` disposition. |
| `rust/rlab`, `rust/rdb`, `rust/projects/*` | Consolidated Rust lab/database/projects. | Map old Rust toy projects or mark deprecated. |
| `docs/*` | Knowledge base, books, reports, build-projects. | Check filenames with spaces/quotes and ensure generated docs are ignored. |
| `dbradar` | Frontend app source without generated deps. | Confirm package lock is intentionally tracked. |
| `cuda` | GPU setup and verification scripts. | Check whether `.deb` installer should be kept in repo. |

## Local Data And Binary Review

These files remain in the working tree and should be decided explicitly:

| Path | Size | Suggested action |
| --- | ---: | --- |
| `cc/golab/bin/leetcode_433` | 1.9M | Delete; compiled binary. |
| `cc/projects/learn-balel/bazelisk` | 6.3M | Prefer install instructions or external tool cache. |
| `cc/tools/duckdb/metadata.ducklake` | 4.0M | Keep only if it is a required sample fixture; otherwise regenerate locally. |
| `python/projects/py-radar/data/items.duckdb` | 9.3M | Treat as local generated data; keep ignored and do not stage. |
| `python/pylab/tools/sr/fe.audit.log` | small | Delete; log file. |
| `cuda/amdgpu-install_6.2.60200-1_all.deb` | unknown here | Review carefully; installers usually should not live in git. |

## Recommended Next Actions

1. Review and mark each `Needs review` row as `moved`, `deprecated`, or
   `restore`.
2. Stage moved/new source trees in coherent commits by language or project
   family, not as one giant mixed change.
3. Delete local-only binaries/logs after confirmation.
4. Add a lightweight `tools/healthcheck.sh` to preserve the cleanup quality:
   repo size, generated dirs, bad symlinks, `.gitmodules` duplicate paths,
   `.env` tracking, and large-file warnings.

## Open Questions

- Should Java LeetCode/thread examples remain as Java learning material, or is
  `cc/algo` now the canonical algorithm lab?
- Is `cc/sr` obsolete, or should it move under `cc/projects` or `docs`?
- Should `python/sqlparser` become part of `python/projects/py-toydb`?
- Should Rust intro projects be archived in docs, moved under `rust/projects`,
  or dropped entirely?
- Are the CUDA installer artifacts reproducible enough to replace with download
  instructions?
