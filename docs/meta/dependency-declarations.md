# Dependency consumer audit: xlab main bf3e2ed45c12cc551fd44ef3cb89366970cd92ba

Current operational contracts supersede the historical declaration counts below:
see [2026-10-19 dependency contracts](dependencies-current.md). Historical evidence
and recommendations below remain tied to their original baseline.

Snapshot note: the five-project owner decision on 2026-10-15 supersedes earlier
retention statements for FragmentTutor, Umbra, subway-game, llm-runtime and
py-academic. Historical evidence below remains tied to its stated commit; see
[the retirement record](../migrations/2026-10-15-five-project-retirement.md).

The underlying review was read-only: no installs, downloads or builds. This cleanup archives only the 29 recommended orphan declaration blocks into [the complete inventory](dependency-declarations.json); 38 unresolved orphan declarations and two pinned gitlinks remain. All 2,681 blobs match the verified baseline; 2,631 UTF-8 files were searched and matching build/source routes inspected.

## Decision summary

- 69 declarations, 2 real pinned gitlinks, 67 orphan declarations.
- Orphan classifications: {'active_consumer': 12, 'no_detected_consumer': 33, 'reference_example_only': 22}.
- Recommendations: {'retain': 38, 'archive-declaration': 29}; no outright information-deleting removal is recommended.
- Preserve GoogleTest and Benchmark gitlinks and pins exactly.
- Retain the four direct legacy CMake inputs: glog, abseil-cpp, fmt, folly. Retain fast_float until its manual bootstrap intent is resolved.
- External package and vendored consumers must survive any declaration archival. A package import is not evidence that its orphan source checkout is required.
- Unknown rows stay unknown. Do not archive them solely to make healthcheck green.

## Bounded declaration archival

Candidate scope: 29 declarations, after preserving original path, URL, baseline and evidence in a tracked catalog. This changes .gitmodules metadata only; there is no source checkout at these paths in the audited tree.

cc/thirdparty/robin-hood-hashing, cc/thirdparty/concurrentqueue, cc/thirdparty/C-Plus-Plus, cc/thirdparty/sqlite, cc/thirdparty/simde, cc/thirdparty/seastar, cc/thirdparty/babylon, cc/thirdparty/boost, cc/thirdparty/libchef, cc/thirdparty/rocksdb, cc/thirdparty/brpc, cc/thirdparty/velox, cc/thirdparty/muduo, rust/thirdparty/dbeel, rust/thirdparty/feldera, rust/thirdparty/timely-dataflow, rust/thirdparty/differential-dataflow, rust/thirdparty/osblog, rust/thirdparty/risingwave, rust/thirdparty/materialize, rust/thirdparty/datafusion, python/thirdparty/tinydb, cc/thirdparty/duckdb, cc/thirdparty/datasketch-cpp, cc/thirdparty/doris, cc/thirdparty/arrow, cc/thirdparty/Clickhouse, cc/thirdparty/leveldb, rust/thirdparty/tantivy

If all 29 are archived, expect 40 declarations / 2 gitlinks / 38 orphan failures. Keep remaining failures visible.

## Important caveats

- Legacy cclab remains outside the root portable build and still needs absent local dependencies plus external system packages. This audit does not make it buildable.
- io-uring independently fetches fmt master: mutable and separate from root dependency pins.
- shell/docker/build_folly.sh adds fast_float then copies from a mismatched relative path; it also performs apt installation and git mutation. It was not executed.
- robin-hood-hashing is an active tracked 3.11.5 header with MIT attribution; never remove it along with its orphan declaration.
- Python ToyDB is unrelated to the Rust erikgrinaker/toydb orphan. System sqlite3, PyArrow, Cargo Arrow/DataFusion/Tantivy and DuckDB wheels do not consume their orphan source paths.
- Moved research files in an earlier audit were not counted as current positive evidence; optd and TheAlgorithms/Python consequently remain unresolved.

## Per-dependency findings

### cc/thirdparty/benchmark
- Status: pinned gitlink; active_consumer; binding: tracked_gitlink_and_build_input
- Recommendation: **retain**
- Original URL: `https://github.com/google/benchmark.git`
- Why: Keep the real gitlink and declaration unchanged. Root benchmark helper and legacy ccbench use it.
- Gitlink: `c58e6d0710581e3a08d65c349664128a8d9a2461`
- Existing version evidence: c58e6d0710581e3a08d65c349664128a8d9a2461
- Evidence: [cmake/XlabDependencies.cmake:44](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cmake/XlabDependencies.cmake#L44); [cc/ccbench/CMakeLists.txt:138](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/ccbench/CMakeLists.txt#L138); [cc/cclab/src/CMakeLists.txt:6](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/cclab/src/CMakeLists.txt#L6)

### cc/thirdparty/glog
- Status: orphan; active_consumer; binding: direct_legacy_cmake_checkout
- Recommendation: **retain**
- Original URL: `git@github.com:google/glog.git`
- Why: The absent checkout is still an unconditional configure input to legacy cclab and ccbench. Retain until those build contracts are repaired or intentionally retired; do not invent an upstream pin.
- Evidence: [cc/cclab/CMakeLists.txt:149](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/cclab/CMakeLists.txt#L149); [cc/ccbench/CMakeLists.txt:134](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/ccbench/CMakeLists.txt#L134)

### cc/thirdparty/googletest
- Status: pinned gitlink; active_consumer; binding: tracked_gitlink_and_build_input
- Recommendation: **retain**
- Original URL: `https://github.com/google/googletest.git`
- Why: Keep the real gitlink and declaration unchanged. Root CMake and independent C++ tests consume it; the explicit fetch/installed-package fallback is still supported.
- Gitlink: `b514bdc898e2951020cbdca1304b75f5950d1f59`
- Existing version evidence: b514bdc898e2951020cbdca1304b75f5950d1f59
- Evidence: [cmake/XlabDependencies.cmake:33](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cmake/XlabDependencies.cmake#L33); [cc/projects/mini-seastar/CMakeLists.txt:48](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/projects/mini-seastar/CMakeLists.txt#L48); [cc/ccbench/CMakeLists.txt:135](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/ccbench/CMakeLists.txt#L135)

### cc/thirdparty/robin-hood-hashing
- Status: orphan; active_consumer; binding: tracked_vendored_header_not_orphan_checkout
- Recommendation: **archive-declaration**
- Original URL: `git@github.com:martinus/robin-hood-hashing.git`
- Why: The live consumer includes an already tracked local header. Archive only the orphan declaration; preserve the header, tests, MIT attribution and version. The external add_subdirectory is commented out.
- Existing version evidence: Vendored header 3.11.5; upstream commit not recorded
- Evidence: [cc/cclab/src/common/map/robin_hood_map.h:9](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/cclab/src/common/map/robin_hood_map.h#L9); [cc/cclab/src/common/map/robin_hood_map.h:33](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/cclab/src/common/map/robin_hood_map.h#L33); [cc/cclab/test/common/robin_hood_map_test.cc:16](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/cclab/test/common/robin_hood_map_test.cc#L16); [cc/cclab/CMakeLists.txt:151](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/cclab/CMakeLists.txt#L151)

### cc/thirdparty/abseil-cpp
- Status: orphan; active_consumer; binding: direct_legacy_cmake_checkout
- Recommendation: **retain**
- Original URL: `git@github.com:abseil/abseil-cpp.git`
- Why: Legacy cclab adds the missing local checkout and links absl::node_hash_map in live tests. The installed-package route in srlab is separate.
- Evidence: [cc/cclab/CMakeLists.txt:152](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/cclab/CMakeLists.txt#L152); [cc/cclab/test/CMakeLists.txt:8](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/cclab/test/CMakeLists.txt#L8); [cc/cclab/test/common/abseil_test.cc:14](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/cclab/test/common/abseil_test.cc#L14); [cc/srlab/CMakeLists.txt:72](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/srlab/CMakeLists.txt#L72)

### c/minilisp
- Status: orphan; no_detected_consumer; binding: not_established
- Recommendation: **retain**
- Original URL: `git@github.com:rui314/minilisp.git`
- Why: Only declaration/inventory evidence was found; no build, import, executable source-path or specific source-reading consumer was established. Retain pending owner intent or stronger evidence; absence of a detected consumer is not proof of uselessness.
- Evidence: Declaration at .gitmodules:32; no specific consumer established after the scoped scan.

### c/chibicc
- Status: orphan; no_detected_consumer; binding: not_established
- Recommendation: **retain**
- Original URL: `git@github.com:rui314/chibicc.git`
- Why: Only declaration/inventory evidence was found; no build, import, executable source-path or specific source-reading consumer was established. Retain pending owner intent or stronger evidence; absence of a detected consumer is not proof of uselessness.
- Evidence: Declaration at .gitmodules:35; no specific consumer established after the scoped scan.

### cc/thirdparty/gperftools
- Status: orphan; no_detected_consumer; binding: not_established
- Recommendation: **retain**
- Original URL: `git@github.com:gperftools/gperftools.git`
- Why: Only a commented add_subdirectory besides inventory; comments do not establish an active dependency. Retain pending owner intent or stronger evidence; absence of a detected consumer is not proof of uselessness.
- Evidence: [cc/cclab/CMakeLists.txt:156](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/cclab/CMakeLists.txt#L156)

### cc/thirdparty/concurrentqueue
- Status: orphan; reference_example_only; binding: no_declared_checkout_consumer_detected
- Recommendation: **archive-declaration**
- Original URL: `git@github.com:cameron314/concurrentqueue.git`
- Why: DuckDB reading notes explicitly describe moodycamel::ConcurrentQueue. The identically named local test class is defined inline and does not include the upstream queue header.
- Evidence: [docs/reports/duckdb/reading-ducdb.md:1236](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/docs/reports/duckdb/reading-ducdb.md#L1236); [cc/cclab/test/common/boost_test.cc:67](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/cclab/test/common/boost_test.cc#L67)

### cc/thirdparty/x86-simd-sort
- Status: orphan; no_detected_consumer; binding: not_established
- Recommendation: **retain**
- Original URL: `git@github.com:intel/x86-simd-sort.git`
- Why: Only declaration/inventory evidence was found; no build, import, executable source-path or specific source-reading consumer was established. Retain pending owner intent or stronger evidence; absence of a detected consumer is not proof of uselessness.
- Evidence: Declaration at .gitmodules:46; no specific consumer established after the scoped scan.

### cc/thirdparty/clang_combined_time_trace
- Status: orphan; no_detected_consumer; binding: not_established
- Recommendation: **retain**
- Original URL: `git@github.com:woodroof/clang_combined_time_trace.git`
- Why: Only declaration/inventory evidence was found; no build, import, executable source-path or specific source-reading consumer was established. Retain pending owner intent or stronger evidence; absence of a detected consumer is not proof of uselessness.
- Evidence: Declaration at .gitmodules:49; no specific consumer established after the scoped scan.

### cc/thirdparty/ClangBuildAnalyzer
- Status: orphan; no_detected_consumer; binding: not_established
- Recommendation: **retain**
- Original URL: `git@github.com:aras-p/ClangBuildAnalyzer.git`
- Why: Only declaration/inventory evidence was found; no build, import, executable source-path or specific source-reading consumer was established. Retain pending owner intent or stronger evidence; absence of a detected consumer is not proof of uselessness.
- Evidence: Declaration at .gitmodules:52; no specific consumer established after the scoped scan.

### cc/thirdparty/C-Plus-Plus
- Status: orphan; reference_example_only; binding: no_declared_checkout_consumer_detected
- Recommendation: **archive-declaration**
- Original URL: `git@github.com:TheAlgorithms/C-Plus-Plus.git`
- Why: Explicit external reading/source link; no executable consumer of the declared checkout found. Preserve original URL/path in a reference catalog before removing the orphan declaration.
- Evidence: [cc/README.md:32](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/README.md#L32)

### cc/thirdparty/wren
- Status: orphan; no_detected_consumer; binding: not_established
- Recommendation: **retain**
- Original URL: `git@github.com:wren-lang/wren.git`
- Why: Only declaration/inventory evidence was found; no build, import, executable source-path or specific source-reading consumer was established. Retain pending owner intent or stronger evidence; absence of a detected consumer is not proof of uselessness.
- Evidence: Declaration at .gitmodules:58; no specific consumer established after the scoped scan.

### cc/thirdparty/libcoro
- Status: orphan; no_detected_consumer; binding: not_established
- Recommendation: **retain**
- Original URL: `git@github.com:jbaldwin/libcoro.git`
- Why: Only declaration/inventory evidence was found; no build, import, executable source-path or specific source-reading consumer was established. Retain pending owner intent or stronger evidence; absence of a detected consumer is not proof of uselessness.
- Evidence: Declaration at .gitmodules:61; no specific consumer established after the scoped scan.

### cc/thirdparty/sqlite
- Status: orphan; active_consumer; binding: python_stdlib_runtime_not_orphan_checkout
- Recommendation: **archive-declaration**
- Original URL: `git@github.com:sqlite/sqlite.git`
- Why: py-stock and pylab use Python sqlite3. This runtime binding does not build cc/thirdparty/sqlite. Archive the source-declaration metadata only; preserve SQLite-backed applications and data handling.
- Evidence: [python/projects/py-stock/db.py:1](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/python/projects/py-stock/db.py#L1); [python/pylab/test/test_cryptography.py:1](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/python/pylab/test/test_cryptography.py#L1)

### cc/thirdparty/hardware-effects
- Status: orphan; no_detected_consumer; binding: not_established
- Recommendation: **retain**
- Original URL: `git@github.com:Kobzol/hardware-effects.git`
- Why: Only declaration/inventory evidence was found; no build, import, executable source-path or specific source-reading consumer was established. Retain pending owner intent or stronger evidence; absence of a detected consumer is not proof of uselessness.
- Evidence: Declaration at .gitmodules:67; no specific consumer established after the scoped scan.

### cc/thirdparty/liburing4cpp
- Status: orphan; no_detected_consumer; binding: not_established
- Recommendation: **retain**
- Original URL: `git@github.com:CarterLi/liburing4cpp.git`
- Why: The io-uring project has its own include/io_uring implementation and links system uring. That does not establish usage of CarterLi/liburing4cpp. Retain pending owner intent or stronger evidence; absence of a detected consumer is not proof of uselessness.
- Evidence: [cc/projects/io-uring/CMakeLists.txt:33](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/projects/io-uring/CMakeLists.txt#L33)

### cc/thirdparty/Radix-Hash-Join
- Status: orphan; no_detected_consumer; binding: not_established
- Recommendation: **retain**
- Original URL: `git@github.com:giorgospan/Radix-Hash-Join.git`
- Why: Only declaration/inventory evidence was found; no build, import, executable source-path or specific source-reading consumer was established. Retain pending owner intent or stronger evidence; absence of a detected consumer is not proof of uselessness.
- Evidence: Declaration at .gitmodules:73; no specific consumer established after the scoped scan.

### cc/thirdparty/simde
- Status: orphan; reference_example_only; binding: no_declared_checkout_consumer_detected
- Recommendation: **archive-declaration**
- Original URL: `git@github.com:simd-everywhere/simde.git`
- Why: Explicit external reading/source link; no executable consumer of the declared checkout found. Preserve original URL/path in a reference catalog before removing the orphan declaration.
- Evidence: [cc/README.md:36](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/README.md#L36)

### cc/thirdparty/seastar
- Status: orphan; reference_example_only; binding: no_declared_checkout_consumer_detected
- Recommendation: **archive-declaration**
- Original URL: `git@github.com:LiShuMing/seastar.git`
- Why: MiniSeastar is documented as inspired by Seastar and is locally implemented. Its CMake file uses its own sources and GoogleTest, not the orphan Seastar checkout.
- Evidence: [cc/projects/mini-seastar/AGENTS.md:9](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/projects/mini-seastar/AGENTS.md#L9); [cc/projects/mini-seastar/CMakeLists.txt:35](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/projects/mini-seastar/CMakeLists.txt#L35)

### cc/thirdparty/noisepage
- Status: orphan; no_detected_consumer; binding: not_established
- Recommendation: **retain**
- Original URL: `git@github.com:cmu-db/noisepage.git`
- Why: Only declaration/inventory evidence was found; no build, import, executable source-path or specific source-reading consumer was established. Retain pending owner intent or stronger evidence; absence of a detected consumer is not proof of uselessness.
- Evidence: Declaration at .gitmodules:82; no specific consumer established after the scoped scan.

### cc/thirdparty/fmt
- Status: orphan; active_consumer; binding: direct_legacy_cmake_checkout_plus_independent_routes
- Recommendation: **retain**
- Original URL: `git@github.com:fmtlib/fmt.git`
- Why: Legacy cclab requires this checkout. io-uring independently fetches fmt master; Bazel and srlab use independent packages. Do not remove the declaration while the local build contract remains.
- Existing version evidence: Bazel fmt 10.2.1; io-uring master is mutable, not pinned
- Evidence: [cc/cclab/CMakeLists.txt:145](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/cclab/CMakeLists.txt#L145); [cc/projects/io-uring/CMakeLists.txt:18](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/projects/io-uring/CMakeLists.txt#L18); [cc/projects/learn-balel/MODULE.bazel:7](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/projects/learn-balel/MODULE.bazel#L7); [cc/srlab/CMakeLists.txt:66](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/srlab/CMakeLists.txt#L66)

### cc/thirdparty/babylon
- Status: orphan; reference_example_only; binding: no_declared_checkout_consumer_detected
- Recommendation: **archive-declaration**
- Original URL: `git@github.com:baidu/babylon.git`
- Why: Explicit external reading/source link; no executable consumer of the declared checkout found. Preserve original URL/path in a reference catalog before removing the orphan declaration.
- Evidence: [cc/README.md:34](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/README.md#L34)

### cc/thirdparty/boost
- Status: orphan; active_consumer; binding: installed_external_package_not_orphan_checkout
- Recommendation: **archive-declaration**
- Original URL: `git@github.com:boostorg/boost.git`
- Why: srlab consumes installed Boost and Folly setup installs system packages. No live use of the declared source checkout was found; archive its metadata while keeping package configuration and consumers.
- Existing version evidence: srlab requires Boost >=1.80, hints Boost-1.80.0
- Evidence: [cc/srlab/CMakeLists.txt:78](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/srlab/CMakeLists.txt#L78); [cc/srlab/tests/CMakeLists.txt:57](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/srlab/tests/CMakeLists.txt#L57); [shell/docker/build_folly.sh:10](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/shell/docker/build_folly.sh#L10); [cc/cclab/CMakeLists.txt:160](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/cclab/CMakeLists.txt#L160)

### cc/thirdparty/flight-benchmark
- Status: orphan; no_detected_consumer; binding: not_established
- Recommendation: **retain**
- Original URL: `git@github.com:vichry2/flight-benchmark.git`
- Why: Only declaration/inventory evidence was found; no build, import, executable source-path or specific source-reading consumer was established. Retain pending owner intent or stronger evidence; absence of a detected consumer is not proof of uselessness.
- Evidence: Declaration at .gitmodules:94; no specific consumer established after the scoped scan.

### cc/thirdparty/junction
- Status: orphan; no_detected_consumer; binding: not_established
- Recommendation: **retain**
- Original URL: `git@github.com:preshing/junction.git`
- Why: Physics semiconductor junctions and a word-DFA junction variable are false-positive names, not preshing/junction use. Retain pending owner intent or stronger evidence; absence of a detected consumer is not proof of uselessness.
- Evidence: Declaration at .gitmodules:97; no specific consumer established after the scoped scan.

### cc/thirdparty/libchef
- Status: orphan; reference_example_only; binding: no_declared_checkout_consumer_detected
- Recommendation: **archive-declaration**
- Original URL: `git@github.com:q191201771/libchef.git`
- Why: Explicit external reading/source link; no executable consumer of the declared checkout found. Preserve original URL/path in a reference catalog before removing the orphan declaration.
- Evidence: [cc/README.md:29](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/README.md#L29)

### cc/thirdparty/simple-sqlite
- Status: orphan; no_detected_consumer; binding: not_established
- Recommendation: **retain**
- Original URL: `git@github.com:madushadhanushka/simple-sqlite.git`
- Why: Only declaration/inventory evidence was found; no build, import, executable source-path or specific source-reading consumer was established. Retain pending owner intent or stronger evidence; absence of a detected consumer is not proof of uselessness.
- Evidence: Declaration at .gitmodules:103; no specific consumer established after the scoped scan.

### cc/thirdparty/templight-tools
- Status: orphan; no_detected_consumer; binding: not_established
- Recommendation: **retain**
- Original URL: `git@github.com:mikael-s-persson/templight-tools.git`
- Why: Only declaration/inventory evidence was found; no build, import, executable source-path or specific source-reading consumer was established. Retain pending owner intent or stronger evidence; absence of a detected consumer is not proof of uselessness.
- Evidence: Declaration at .gitmodules:106; no specific consumer established after the scoped scan.

### cc/thirdparty/rocksdb
- Status: orphan; reference_example_only; binding: no_declared_checkout_consumer_detected
- Recommendation: **archive-declaration**
- Original URL: `git@github.com:facebook/rocksdb.git`
- Why: Current research discusses RocksDB/Pebble storage engines. No local source-checkout consumer detected; reference use does not establish that the project is inactive.
- Evidence: [docs/reading-open-source/crockroachdb/deepdive-2025.md:16](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/docs/reading-open-source/crockroachdb/deepdive-2025.md#L16)

### cc/thirdparty/mimalloc
- Status: orphan; no_detected_consumer; binding: not_established
- Recommendation: **retain**
- Original URL: `git@github.com:microsoft/mimalloc.git`
- Why: Only declaration/inventory evidence was found; no build, import, executable source-path or specific source-reading consumer was established. Retain pending owner intent or stronger evidence; absence of a detected consumer is not proof of uselessness.
- Evidence: Declaration at .gitmodules:112; no specific consumer established after the scoped scan.

### cc/thirdparty/lua
- Status: orphan; no_detected_consumer; binding: not_established
- Recommendation: **retain**
- Original URL: `git@github.com:lua/lua.git`
- Why: Source-file analysis support and a sysbench .lua invocation do not establish usage of the lua/lua source checkout; sysbench interpreter implementation was not audited. Retain pending owner intent or stronger evidence; absence of a detected consumer is not proof of uselessness.
- Evidence: [python/projects/py-academic/crazy_functions/SourceCode_Analyse.py:315](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/python/projects/py-academic/crazy_functions/SourceCode_Analyse.py#L315); [python/pylab/tools/benchmark/sysbench.sh:1](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/python/pylab/tools/benchmark/sysbench.sh#L1)

### cc/thirdparty/brpc
- Status: orphan; reference_example_only; binding: no_declared_checkout_consumer_detected
- Recommendation: **archive-declaration**
- Original URL: `git@github.com:apache/brpc.git`
- Why: A dedicated source-reading report exists; legacy add_subdirectory is commented out. Archive only declaration metadata and preserve report/source links.
- Evidence: [docs/reports/brpc/readming-brpc.md:1](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/docs/reports/brpc/readming-brpc.md#L1); [cc/cclab/CMakeLists.txt:158](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/cclab/CMakeLists.txt#L158)

### cc/thirdparty/velox
- Status: orphan; reference_example_only; binding: no_declared_checkout_consumer_detected
- Recommendation: **archive-declaration**
- Original URL: `git@github.com:facebookincubator/velox.git`
- Why: Active reading/report navigation points to Cygnus, with additional xlab source-analysis notes. No local executable checkout binding found.
- Evidence: [docs/README.md:28](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/docs/README.md#L28); [docs/reading-open-source/velox/reading-velox.md:1](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/docs/reading-open-source/velox/reading-velox.md#L1)

### cc/thirdparty/muduo
- Status: orphan; reference_example_only; binding: no_declared_checkout_consumer_detected
- Recommendation: **archive-declaration**
- Original URL: `git@github.com:chenshuo/muduo.git`
- Why: A C++ learning resource explicitly names chenshuo/muduo and Reactor study. No build consumer of the declared checkout was found.
- Evidence: [docs/how-to-do/how-to-learn/learn-cpp-resources.md:177](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/docs/how-to-do/how-to-learn/learn-cpp-resources.md#L177)

### cc/thirdparty/dlmalloc
- Status: orphan; no_detected_consumer; binding: not_established
- Recommendation: **retain**
- Original URL: `git@github.com:ennorehling/dlmalloc.git`
- Why: Only declaration/inventory evidence was found; no build, import, executable source-path or specific source-reading consumer was established. Retain pending owner intent or stronger evidence; absence of a detected consumer is not proof of uselessness.
- Evidence: Declaration at .gitmodules:127; no specific consumer established after the scoped scan.

### rust/thirdparty/dbeel
- Status: orphan; reference_example_only; binding: no_declared_checkout_consumer_detected
- Recommendation: **archive-declaration**
- Original URL: `git@github.com:tontinton/dbeel.git`
- Why: Explicit external reading/source link; no executable consumer of the declared checkout found. Preserve original URL/path in a reference catalog before removing the orphan declaration.
- Evidence: [cc/README.md:35](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/README.md#L35)

### rust/thirdparty/feldera
- Status: orphan; reference_example_only; binding: no_declared_checkout_consumer_detected
- Recommendation: **archive-declaration**
- Original URL: `git@github.com:feldera/feldera.git`
- Why: The materialized-view research identifies Feldera as the DBSP implementation. No registry or local-checkout executable consumer detected.
- Evidence: [docs/build-projects/reports/materialized_views/ivm/ivm_report2.md:71](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/docs/build-projects/reports/materialized_views/ivm/ivm_report2.md#L71)

### rust/thirdparty/timely-dataflow
- Status: orphan; reference_example_only; binding: no_declared_checkout_consumer_detected
- Recommendation: **archive-declaration**
- Original URL: `git@github.com:TimelyDataflow/timely-dataflow.git`
- Why: RisingWave comparison references the TimelyDataflow ecosystem. This is conceptual research evidence, not a local Cargo dependency or source-path usage.
- Evidence: [docs/reports/risingwave/deepdive-2025.md:414](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/docs/reports/risingwave/deepdive-2025.md#L414)

### rust/thirdparty/arroyo
- Status: orphan; no_detected_consumer; binding: not_established
- Recommendation: **retain**
- Original URL: `git@github.com:ArroyoSystems/arroyo.git`
- Why: Only declaration/inventory evidence was found; no build, import, executable source-path or specific source-reading consumer was established. Retain pending owner intent or stronger evidence; absence of a detected consumer is not proof of uselessness.
- Evidence: Declaration at .gitmodules:141; no specific consumer established after the scoped scan.

### rust/thirdparty/optd
- Status: orphan; no_detected_consumer; binding: not_established
- Recommendation: **retain**
- Original URL: `git@github.com:cmu-db/optd.git`
- Why: The prior audit found only a repo-list link in migrated python/projects/py-tools/git-repos.md. That file is absent on this baseline. No current checkout consumer established. Retain pending owner intent or stronger evidence; absence of a detected consumer is not proof of uselessness.
- Evidence: Declaration at .gitmodules:144; no specific consumer established after the scoped scan.

### rust/thirdparty/sqleibniz
- Status: orphan; no_detected_consumer; binding: not_established
- Recommendation: **retain**
- Original URL: `git@github.com:xNaCly/sqleibniz.git`
- Why: Only declaration/inventory evidence was found; no build, import, executable source-path or specific source-reading consumer was established. Retain pending owner intent or stronger evidence; absence of a detected consumer is not proof of uselessness.
- Evidence: Declaration at .gitmodules:147; no specific consumer established after the scoped scan.

### rust/thirdparty/differential-dataflow
- Status: orphan; reference_example_only; binding: no_declared_checkout_consumer_detected
- Recommendation: **archive-declaration**
- Original URL: `https://github.com/TimelyDataflow/differential-dataflow.git`
- Why: RisingWave comparison names Differential Dataflow and Frank McSherry. No Cargo dependency on the declared checkout found.
- Evidence: [docs/reports/risingwave/deepdive-2025.md:422](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/docs/reports/risingwave/deepdive-2025.md#L422)

### rust/thirdparty/osblog
- Status: orphan; reference_example_only; binding: no_declared_checkout_consumer_detected
- Recommendation: **archive-declaration**
- Original URL: `git@github.com:sgmarz/osblog.git`
- Why: Explicit external reading/source link; no executable consumer of the declared checkout found. Preserve original URL/path in a reference catalog before removing the orphan declaration.
- Evidence: [cc/README.md:33](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/README.md#L33)

### rust/thirdparty/toydb
- Status: orphan; no_detected_consumer; binding: not_established
- Recommendation: **retain**
- Original URL: `git@github.com:erikgrinaker/toydb.git`
- Why: Native CI and Python ToyDB refer to the local Python project inspired by TinyDB, not erikgrinaker/toydb. Retain pending owner intent or stronger evidence; absence of a detected consumer is not proof of uselessness.
- Evidence: [python/projects/py-toydb/README.md:7](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/python/projects/py-toydb/README.md#L7)

### rust/thirdparty/risingwave
- Status: orphan; reference_example_only; binding: no_declared_checkout_consumer_detected
- Recommendation: **archive-declaration**
- Original URL: `https://github.com/risingwavelabs/risingwave.git`
- Why: Dedicated code-reading chapters and reports remain on this baseline. Archive source declaration metadata without deleting books/reports or assuming their separate migration is complete.
- Evidence: [docs/books/risingwave-book/chapters/03-SQL解析器.md:11](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/docs/books/risingwave-book/chapters/03-SQL%E8%A7%A3%E6%9E%90%E5%99%A8.md#L11); [docs/reports/risingwave/deepdive-2025.md:408](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/docs/reports/risingwave/deepdive-2025.md#L408)

### rust/thirdparty/materialize
- Status: orphan; reference_example_only; binding: no_declared_checkout_consumer_detected
- Recommendation: **archive-declaration**
- Original URL: `https://github.com/MaterializeInc/materialize.git`
- Why: The RisingWave comparison clearly refers to the Materialize product, distinct from generic SQL materialization or similarly named functions. No executable checkout consumer found.
- Evidence: [docs/reports/risingwave/deepdive-2025.md:408](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/docs/reports/risingwave/deepdive-2025.md#L408)

### rust/thirdparty/datafusion
- Status: orphan; active_consumer; binding: cargo_registry_not_orphan_checkout
- Recommendation: **archive-declaration**
- Original URL: `git@github.com:apache/datafusion.git`
- Why: Umbra directly depends on DataFusion and lance-datafusion through registry versions; preserve manifests/lockfile. Research references do not require a gitlink at rust/thirdparty/datafusion.
- Existing version evidence: datafusion = 43; lance-datafusion = 0.20; lockfile present
- Evidence: [rust/projects/umbra/Cargo.toml:18](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/rust/projects/umbra/Cargo.toml#L18); [rust/projects/umbra/umbra-core/Cargo.toml:14](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/rust/projects/umbra/umbra-core/Cargo.toml#L14); [docs/README.md:26](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/docs/README.md#L26)

### python/thirdparty/tinydb
- Status: orphan; reference_example_only; binding: no_declared_checkout_consumer_detected
- Recommendation: **archive-declaration**
- Original URL: `git@github.com:msiemens/tinydb.git`
- Why: Python ToyDB explicitly cites TinyDB as its inspiration and uses its own tracked relative imports. Preserve its implementation and attribution; archive only the upstream source declaration.
- Evidence: [python/projects/py-toydb/README.md:7](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/python/projects/py-toydb/README.md#L7); [python/projects/py-toydb/pyproject.toml:42](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/python/projects/py-toydb/pyproject.toml#L42); [python/projects/py-toydb/toydb/db.py:4](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/python/projects/py-toydb/toydb/db.py#L4)

### python/thirdparty/pydbsp
- Status: orphan; no_detected_consumer; binding: not_established
- Recommendation: **retain**
- Original URL: `git@github.com:brurucy/pydbsp.git`
- Why: Name occurs in inventory/guidance only; no import, package dependency or source-checkout consumer found. Retain pending owner intent or stronger evidence; absence of a detected consumer is not proof of uselessness.
- Evidence: Declaration at .gitmodules:173; no specific consumer established after the scoped scan.

### python/thirdparty/Python
- Status: orphan; no_detected_consumer; binding: not_established
- Recommendation: **retain**
- Original URL: `git@github.com:TheAlgorithms/Python.git`
- Why: Generic Python language mentions are not TheAlgorithms/Python use. The prior repo-list reference migrated out with py-tools; no current specific consumer established. Retain pending owner intent or stronger evidence; absence of a detected consumer is not proof of uselessness.
- Evidence: Declaration at .gitmodules:176; no specific consumer established after the scoped scan.

### cc/thirdparty/duckdb
- Status: orphan; active_consumer; binding: python_registry_package_and_research_reference
- Recommendation: **archive-declaration**
- Original URL: `git@github.com:duckdb/duckdb.git`
- Why: Python imports the installed DuckDB package; research documents discuss its internals. Neither route consumes cc/thirdparty/duckdb. Preserve installed-package requirements and remaining research links.
- Existing version evidence: duckdb == 1.1.3 in pylab requirements
- Evidence: [python/pylab/requirements.txt:20](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/python/pylab/requirements.txt#L20); [python/pylab/test/test_duckdb.py:1](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/python/pylab/test/test_duckdb.py#L1); [docs/README.md:23](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/docs/README.md#L23)

### cc/thirdparty/duckdb_ivm
- Status: orphan; no_detected_consumer; binding: not_established
- Recommendation: **retain**
- Original URL: `git@github.com:ila/duckdb.git`
- Why: DuckDB package imports/reports do not establish use of the separate ila/duckdb fork. Retain pending owner intent or stronger evidence; absence of a detected consumer is not proof of uselessness.
- Evidence: Declaration at .gitmodules:184; no specific consumer established after the scoped scan.

### cc/thirdparty/perf-tools
- Status: orphan; no_detected_consumer; binding: not_established
- Recommendation: **retain**
- Original URL: `git@github.com:brendangregg/perf-tools.git`
- Why: Only declaration/inventory evidence was found; no build, import, executable source-path or specific source-reading consumer was established. Retain pending owner intent or stronger evidence; absence of a detected consumer is not proof of uselessness.
- Evidence: Declaration at .gitmodules:187; no specific consumer established after the scoped scan.

### rust/thirdparty/denormalized
- Status: orphan; no_detected_consumer; binding: not_established
- Recommendation: **retain**
- Original URL: `git@github.com:probably-nothing-labs/denormalized.git`
- Why: Only declaration/inventory evidence was found; no build, import, executable source-path or specific source-reading consumer was established. Retain pending owner intent or stronger evidence; absence of a detected consumer is not proof of uselessness.
- Evidence: Declaration at .gitmodules:190; no specific consumer established after the scoped scan.

### cc/thirdparty/datasketch-cpp
- Status: orphan; reference_example_only; binding: no_declared_checkout_consumer_detected
- Recommendation: **archive-declaration**
- Original URL: `git@github.com:apache/datasketches-cpp.git`
- Why: DataSketches is discussed in Iceberg/Puffin and IVM research. This proves a project-family reference, not consumption of the specific C++ checkout.
- Evidence: [docs/reports/iceberg/iceberg-deep-dive.md:189](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/docs/reports/iceberg/iceberg-deep-dive.md#L189); [docs/build-projects/reports/materialized_views/ivm/ivm_report2.md:424](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/docs/build-projects/reports/materialized_views/ivm/ivm_report2.md#L424)

### cc/thirdparty/doris
- Status: orphan; reference_example_only; binding: no_declared_checkout_consumer_detected
- Recommendation: **archive-declaration**
- Original URL: `git@github.com:apache/doris.git`
- Why: The libunwind experiment cites a specific Doris PR as a possible implementation source; dedicated Doris research also remains. No direct dependency on this checkout found.
- Evidence: [cc/cclab/test/tools/libunwind_test.cc:1](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/cclab/test/tools/libunwind_test.cc#L1); [docs/reading-open-source/doris/deepdive-2025.md:1](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/docs/reading-open-source/doris/deepdive-2025.md#L1)

### cc/thirdparty/json
- Status: orphan; no_detected_consumer; binding: not_established
- Recommendation: **retain**
- Original URL: `git@github.com:nlohmann/json.git`
- Why: Generic JSON files and imports are not nlohmann/json. No nlohmann include or manifest binding was found. Retain pending owner intent or stronger evidence; absence of a detected consumer is not proof of uselessness.
- Evidence: Declaration at .gitmodules:199; no specific consumer established after the scoped scan.

### python/thirdparty/parquet-python
- Status: orphan; no_detected_consumer; binding: not_established
- Recommendation: **retain**
- Original URL: `git@github.com:jcrobak/parquet-python.git`
- Why: Parquet data format usage and PyArrow packages do not establish usage of jcrobak/parquet-python. Retain pending owner intent or stronger evidence; absence of a detected consumer is not proof of uselessness.
- Evidence: Declaration at .gitmodules:202; no specific consumer established after the scoped scan.

### cc/thirdparty/parquet-format
- Status: orphan; no_detected_consumer; binding: not_established
- Recommendation: **retain**
- Original URL: `git@github.com:apache/parquet-format.git`
- Why: Arrow/Parquet packages and format mentions do not establish consumption of apache/parquet-format at the declared checkout. Retain pending owner intent or stronger evidence; absence of a detected consumer is not proof of uselessness.
- Evidence: Declaration at .gitmodules:205; no specific consumer established after the scoped scan.

### cc/thirdparty/arrow
- Status: orphan; active_consumer; binding: installed_external_libraries_and_registry_packages
- Recommendation: **archive-declaration**
- Original URL: `git@github.com:apache/arrow.git`
- Why: srlab links installed Arrow static archives; Umbra uses registry Arrow crates, and py-numpy-pandas uses PyArrow. None consumes cc/thirdparty/arrow. Archive source-declaration metadata only.
- Existing version evidence: Umbra Arrow crates 53; PyArrow >=16.0; srlab shared Arrow archive version not pinned
- Evidence: [cc/srlab/tests/CMakeLists.txt:34](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/srlab/tests/CMakeLists.txt#L34); [rust/projects/umbra/Cargo.toml:15](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/rust/projects/umbra/Cargo.toml#L15); [python/projects/py-numpy-pandas/requirements.txt:8](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/python/projects/py-numpy-pandas/requirements.txt#L8)

### cc/thirdparty/Clickhouse
- Status: orphan; reference_example_only; binding: no_declared_checkout_consumer_detected
- Recommendation: **archive-declaration**
- Original URL: `git@github.com:ClickHouse/ClickHouse.git`
- Why: The local Cow implementation explicitly cites ClickHouse/Rust inspiration and book navigation routes to Cygnus. It does not include/build the declared ClickHouse checkout.
- Evidence: [cc/cclab/src/common/cow.h:22](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/cclab/src/common/cow.h#L22); [docs/README.md:20](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/docs/README.md#L20)

### cc/thirdparty/btop
- Status: orphan; no_detected_consumer; binding: not_established
- Recommendation: **retain**
- Original URL: `git@github.com:aristocratos/btop.git`
- Why: Only declaration/inventory evidence was found; no build, import, executable source-path or specific source-reading consumer was established. Retain pending owner intent or stronger evidence; absence of a detected consumer is not proof of uselessness.
- Evidence: Declaration at .gitmodules:214; no specific consumer established after the scoped scan.

### cc/thirdparty/leveldb
- Status: orphan; reference_example_only; binding: no_declared_checkout_consumer_detected
- Recommendation: **archive-declaration**
- Original URL: `git@github.com:google/leveldb.git`
- Why: There is a current LevelDB example in research prose and a commented-out local add_subdirectory. This establishes a reference only, not a working integration; prose correctness was not evaluated.
- Evidence: [cc/cclab/CMakeLists.txt:157](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/cclab/CMakeLists.txt#L157); [docs/books/feiman-book/vol1-ch03-physics-and-other-sciences.md:98](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/docs/books/feiman-book/vol1-ch03-physics-and-other-sciences.md#L98)

### rust/thirdparty/tantivy
- Status: orphan; active_consumer; binding: transitive_cargo_registry_not_orphan_checkout
- Recommendation: **archive-declaration**
- Original URL: `git@github.com:quickwit-oss/tantivy.git`
- Why: Umbra has a locked transitive Tantivy dependency through Lance, not a local path dependency. Preserve the Cargo lockfile and runtime graph.
- Existing version evidence: Cargo.lock Tantivy 0.22.1
- Evidence: [rust/projects/umbra/Cargo.toml:18](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/rust/projects/umbra/Cargo.toml#L18); [rust/projects/umbra/Cargo.lock:5966](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/rust/projects/umbra/Cargo.lock#L5966)

### cc/thirdparty/fastgrind
- Status: orphan; no_detected_consumer; binding: not_established
- Recommendation: **retain**
- Original URL: `git@github.com:adny-code/fastgrind.git`
- Why: Only declaration/inventory evidence was found; no build, import, executable source-path or specific source-reading consumer was established. Retain pending owner intent or stronger evidence; absence of a detected consumer is not proof of uselessness.
- Evidence: Declaration at .gitmodules:223; no specific consumer established after the scoped scan.

### cc/thirdparty/folly
- Status: orphan; active_consumer; binding: default_on_legacy_local_checkout_and_optional_srlab_source
- Recommendation: **retain**
- Original URL: `git@github.com:facebook/folly.git`
- Why: Legacy cclab defaults ENABLE_FOLLY to ON and adds this absent checkout. srlab separately offers an OFF-by-default hard-coded source path. Restoring only Folly cannot satisfy the external transitive dependency bundle.
- Evidence: [cc/cclab/CMakeLists.txt:161](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/cclab/CMakeLists.txt#L161); [cc/srlab/CMakeLists.txt:32](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/srlab/CMakeLists.txt#L32); [cc/srlab/CMakeLists.txt:49](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/cc/srlab/CMakeLists.txt#L49)

### cc/thirdparty/fast_float
- Status: orphan; active_consumer; binding: manual_bootstrap_checkout_intent_unverified
- Recommendation: **retain**
- Original URL: `git@github.com:fastfloat/fast_float.git`
- Why: Manual Folly setup invokes git submodule add at this exact path, then copies from a mismatched relative fast_float/include path. Retain until the bootstrap is repaired or deliberately retired. This is code-level consumer intent, not a working build or an instruction to execute it.
- Evidence: [shell/docker/build_folly.sh:18](https://github.com/LiShuMing/xlab/blob/bf3e2ed45c12cc551fd44ef3cb89366970cd92ba/shell/docker/build_folly.sh#L18)

No dependency source code, vendored headers, package manifests, research notes or user checkout directories are removed. The full healthcheck still reports exactly 38 unresolved orphan declarations; this is not a successful native build certification.
