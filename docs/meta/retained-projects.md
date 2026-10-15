# Retained project classification

Baseline: xlab `bf3e2ed45c12cc551fd44ef3cb89366970cd92ba` (2026-10-15).
This is a source-tree inventory, not build certification, product priority or
permission to migrate/delete. Counts include tracked files, not runtime data.
No project below has an accepted source-to-target mapping for retirement.

| Root | Tracked entries | Classification |
| --- | ---: | --- |
| `cc/algo` | 300 | retained experiment; no accepted migration mapping |
| `cc/ccbench` | 15 | retained experiment; no accepted migration mapping |
| `cc/cclab` | 116 | retained experiment; no accepted migration mapping |
| `cc/nasm` | 19 | retained experiment; no accepted migration mapping |
| `cc/projects/cpython` | 30 | retained experiment; no accepted migration mapping |
| `cc/projects/interpreter` | 16 | retained experiment; no accepted migration mapping |
| `cc/projects/io-uring` | 11 | retained experiment; no accepted migration mapping |
| `cc/projects/learn-balel` | 10 | retained experiment; no accepted migration mapping |
| `cc/projects/llvm-jit` | 17 | retained experiment; no accepted migration mapping |
| `cc/projects/mini-seastar` | 22 | retained experiment; no accepted migration mapping |
| `cc/projects/thread-pool` | 19 | retained experiment; no accepted migration mapping |
| `cc/projects/web-server` | 37 | retained experiment; no accepted migration mapping |
| `cc/projects/write-a-C-interpreter` | 15 | retained experiment; no accepted migration mapping |
| `cc/simd` | 9 | retained experiment; no accepted migration mapping |
| `cc/srlab` | 14 | retained experiment; no accepted migration mapping |
| `go/k8s-lab` | 24 | retained experiment; no accepted migration mapping |
| `haskell/hslab` | 1 | retained experiment; no accepted migration mapping |
| `haskell/projects/dsl-transform` | 7 | retained experiment; no accepted migration mapping |
| `haskell/projects/sql-parser` | 11 | retained experiment; no accepted migration mapping |
| `haskell/projects/stm-engine` | 7 | retained experiment; no accepted migration mapping |
| `java/xlab-iceberg` | 17 | retained experiment; no accepted migration mapping |
| `java/xlab-itest` | 623 | retained experiment; no accepted migration mapping |
| `llm/cuda` | 15 | retained experiment; no accepted migration mapping |
| `python/ivm` | 2 | retained experiment; no accepted migration mapping |
| `python/llm_benchmark` | 39 | retained experiment; no accepted migration mapping |
| `python/projects/llm-lab` | 30 | retained experiment; no accepted migration mapping |
| `python/projects/py-academic` | 374 | vendored third-party fork; preserve attribution; packaging decision open |
| `python/projects/py-cycle-lab` | 27 | retained experiment; no accepted migration mapping |
| `python/projects/py-ego` | 136 | retained experiment; no accepted migration mapping |
| `python/projects/py-lab` | 38 | retained experiment; no accepted migration mapping |
| `python/projects/py-numpy-pandas` | 8 | notebook/data learning project; not an empty shell |
| `python/projects/py-stock` | 21 | retained experiment; no accepted migration mapping |
| `python/projects/py-torch` | 27 | retained experiment; no accepted migration mapping |
| `python/projects/py-toydb` | 19 | retained experiment; no accepted migration mapping |
| `python/projects/strata-review` | 8 | retained experiment; no accepted migration mapping |
| `python/pylab` | 57 | retained experiment; no accepted migration mapping |
| `rust/projects/fragment-tutor` | 63 | retained experiment; no accepted migration mapping |
| `rust/projects/llm-runtime` | 12 | design/scaffold; implementation maturity unverified |
| `rust/projects/subway-game` | 57 | retained experiment; no accepted migration mapping |
| `rust/projects/umbra` | 37 | retained experiment; no accepted migration mapping |
| `rust/rdb` | 23 | retained experiment; no accepted migration mapping |
| `rust/rlab` | 78 | retained experiment; no accepted migration mapping |
| `shell/bin` | 7 | retained experiment; no accepted migration mapping |
| `shell/docker` | 3 | retained experiment; no accepted migration mapping |
| `shell/fio` | 2 | retained experiment; no accepted migration mapping |
| `shell/mysql` | 3 | retained experiment; no accepted migration mapping |

## Accepted book retirement

The former four book roots (76 files) have accepted Cygnus mappings and are
removed without stubs in this consolidated proposal. See the [retirement ledger](../migrations/2026-10-15-remaining-books-retirement.json).

Other docs, migration records, ignore rules, project code and user runtime data
are retained. `py-academic` vendoring and the large `cc/srlab/data/v1.jstack`
remain explicit owner decisions. No equivalence is inferred from names such as
Ego, investment or Umbra appearing in another repository.

Machine-readable snapshot: [retained-projects.json](retained-projects.json).
