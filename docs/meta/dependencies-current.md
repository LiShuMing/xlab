# Current dependency contracts

Reviewed 2026-10-19 against `af9a828` and this working-tree change. The owner
requested all P0/P1 quality fixes. The older consumer audit is preserved as a
historical snapshot, not rewritten as new build evidence.

## Operational dependencies

`.gitmodules` now contains exactly the two tracked gitlinks:

| Dependency | Commit |
| --- | --- |
| GoogleTest | `b514bdc898e2951020cbdca1304b75f5950d1f59` |
| Google Benchmark | `c58e6d0710581e3a08d65c349664128a8d9a2461` |

Initialize only these paths. The existing root `XLAB_FETCH_DEPENDENCIES=ON`
fallback uses the same pins; no other source version is selected automatically.

```bash
git submodule update --init -- cc/thirdparty/googletest cc/thirdparty/benchmark
python3 tools/check_dependencies.py
bash tools/healthcheck.sh
```

## The former 38 orphan declarations

All 69 original dependency records retain their path, URL, declaration blob,
consumer evidence, classification and historical recommendation in
[the catalog](dependency-declarations.json). `current_disposition` records the
current operational choice separately. No dependency source or local checkout
was deleted. No unknown-intent reference was relabeled as useless or proven
buildable. The 33 unknown-intent records remain unknown historical references;
they are searchable catalog entries rather than invalid submodule promises.

| Former orphan category | Current contract |
| --- | --- |
| fmt, glog, abseil-cpp | Legacy CMake accepts installed `fmt::fmt`, `glog::glog`, `absl::node_hash_map` packages or explicit local source trees |
| folly | Explicit opt-in via `ENABLE_FOLLY=ON`; installed `Folly::folly` or explicit local source required |
| fast_float | Installed platform dependency of a manually selected Folly checkout; no `git submodule add` or mismatched source copy |
| 33 records without established consumers | Preserve original evidence and unknown intent in the catalog; no automatic checkout/build |

This resolves invalid Git metadata and missing-source assumptions. It does not
supply a validated version bundle for the full legacy C++ laboratory. Installed
package versions belong to the chosen environment; record them when validating
that environment. Configuration fails with an actionable missing-package message
rather than inventing a version or silently omitting required consumers.

## Supported and legacy builds

Root CMake and standalone cclab now default to the portable subset. Use
`CCLAB_PORTABLE_ONLY=OFF` only for the legacy full laboratory. Its Boost,
libunwind, platform headers and other per-test requirements still need an
appropriate Linux environment. Preserve explicit local source checkouts rather
than overwriting them.

```bash
cmake -S . -B build -DXLAB_FETCH_DEPENDENCIES=ON -DXLAB_SANITIZER=undefined
cmake --build build --parallel 4
ctest --test-dir build --output-on-failure --no-tests=error
# Standalone portable cclab, with the same fixed test dependency:
XLAB_FETCH_DEPENDENCIES=ON BUILD_TYPE=UBSAN ./cc/cclab/build.sh
# Optional legacy environment, with packages selected by CMAKE_PREFIX_PATH:
cmake -S cc/cclab -B build-legacy -DCCLAB_PORTABLE_ONLY=OFF -DCMAKE_BUILD_TYPE=UBSAN
```

Folly's helper accepts an explicit source path and an optional build path:
`bash shell/docker/build_folly.sh /path/to/folly /path/to/build`.
Install platform development packages separately; the helper never runs apt,
changes xlab's index or chooses a remote version.

CI now fails on any orphan declaration; there is no exception accepting 38
failures. Metadata health and build certification remain distinct. Runtime
validation status is recorded in [the matrix](validation-matrix.md).
