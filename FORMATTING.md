# Paths and formatting

Use the existing module layout and nearest formatter configuration. This
repository contains independent experiments and imported code; uniform entry
points and accurate navigation do not require one formatter for every language.

## Paths and entry points

- Discover projects through [PROJECTS.md](PROJECTS.md); use exact case and spelling.
- Link to existing files relative to the document. Mark unwritten pages/directories
  as planned plain text, not clickable entries or claims of implemented features.
- Do not add `.gitkeep` files. Create runtime/output directories in their owning
  code when needed. Empty package initializers and Rust module declarations are
  semantic source files, not directory placeholders.
- Keep historical source paths in migration records, regression checks and ignore
  protections; do not recreate retired roots to satisfy old descriptions.
- Missing configuration must stop an entry point clearly before side effects.
  Do not invent credentials, browser permissions or deployment configuration.
- Do not rename established paths merely for style. A rename needs consumer,
  import, build, workflow and navigation review as its own explicit change.

## Formatter precedence

1. The module's committed formatter/package configuration and local AGENTS/RULES.
2. Existing style of the edited file when the module has no formatter configuration.
3. The conservative editing defaults in [.editorconfig](.editorconfig).

C/C++: use the nearest `.clang-format`; root and cclab styles intentionally differ.
Rust: `cargo fmt --check` in the owning Cargo workspace.
Go: `gofmt -l` on the changed Go files; preserve tabs.
Python: use module Ruff/Black/isort settings as configured, without running competing
formatters blindly. LLM Lab uses its own pyproject settings and 100-column limit.
Java/Kotlin: preserve existing module style; do not introduce a global formatter.
JS/TS: use module scripts/Prettier configuration where available, such as
FragmentTutor. No repo-wide node_modules installation or global line-width rule.
Shell/Make: preserve shell syntax and Make recipe tabs; run `bash -n` on changed
Bash scripts. Batch scripts may retain CRLF. Markdown may use two-space hard breaks.

These are local commands to run when the relevant toolchain is available, not
claims that every language formatter or every optional native module is in CI.

## Lightweight enforcement

Run `python3 tools/check_formatting.py` for staged changes, or:

```sh
python3 tools/check_formatting.py --base <base-commit> --head <head-commit>
python3 -m unittest discover -s tools -p 'test_*.py' -v
```

The checker reads Git objects and diffs, never untracked runtime files. It checks
added-line whitespace plus UTF-8, final newline and line endings of changed text
files. Deletions, binary blobs and gitlinks are ignored. CI supplies explicit
base/head commits; a clean checkout alone does not make a committed diff clean.

Imported thirdparty/vendor sources, py-academic, the vendored robin_hood header,
generated build/dist/target directories, lockfiles and notebooks are excluded.
Do not bulk-reformat them or historical files solely to satisfy a new convention.
Existing unrelated whitespace debt remains; fix it only within separately reviewed
changes. This check is not a language formatter, full path validator or build test.
