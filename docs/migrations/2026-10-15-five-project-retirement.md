# Five project source retirements

The owner explicitly requested complete removal of FragmentTutor, Umbra,
subway-game, llm-runtime and py-academic from xlab, regardless of destination
completeness. Future maintenance belongs outside xlab. This decision supersedes
older retention/completeness holds; it does not assert destination equivalence,
build acceptance or complete migration.

| Former root | Removed tracked files |
| --- | ---: |
| `rust/projects/fragment-tutor` | 63 |
| `rust/projects/umbra` | 37 |
| `rust/projects/subway-game` | 57 |
| `rust/projects/llm-runtime` | 8 |
| `python/projects/py-academic` | 374 |

All 539 tracked files are removed without README stubs. Runtime/untracked data
on user machines was not inspected or removed. Git history and the existing
backup branch remain intact. Restore individual files from source commit
`f20485e3b278e34df0b927c89dba1591d65ba6ba` if needed.

The [exact ledger](2026-10-15-five-project-retirement.json) records paths, modes
and source blob hashes, without copying retired file bodies. Historical migration
and dependency evidence remains dated to its original snapshot. No other project,
unknown orphan dependency declaration or actual gitlink is retired by this change.
