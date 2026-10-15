# Codex/Linux and email/learning source retirement

This local cleanup candidate accounts for 174 tracked source entries: 96 archived
manuscripts, 65 copied/adapted Python entries, and 13 explicitly excluded entries.
The 161 archived/adapted entries have verified destination mappings.
It does not claim all source content was migrated. No replacement stubs remain.
Publishing and merging this cleanup still require approval.

## Accepted target snapshots

- Cygnus [PR #6](https://github.com/LiShuMing/cygnus/pull/6):
  `a96bf87e08dcfa31ee40d1d04adb750a1c7be7c3`,
  [postmerge CI](https://github.com/LiShuMing/cygnus/actions/runs/38651636378) passed.
  All 318 reviewed entries match; 96 manuscript destinations preserve reviewed
  bodies, with two approved Codex path replacements. Manuscripts remain needs-review.
- Lyra [PR #5](https://github.com/LiShuMing/lyra/pull/5):
  `c403bd2699afb7a526ef8b67b3d4f6d8ce9a2ad3`,
  [postmerge CI](https://github.com/LiShuMing/lyra/actions/runs/38651630807) passed.
  All 547 reviewed entries match, including the isolated email and learning modules.
  Production credentials, runtime databases, schedules and accounts were not migrated.

The [machine-readable ledger](2026-10-14-books-email-learning-retirement.json)
records every source path, mode, blob, SHA-256, disposition and destination blob.
All 174 source blobs match both refreshed xlab main
`7f32434e0fdea5e9d957fd806121b68554fa3272` and preserved backup
`fd15e65059ff7d0d01ed48b6347cd75881fb4b36`.

## Maintenance and retained scope

- `docs/books/codex-code-book` and `docs/books/deep-linux-book` are maintained in
  [Cygnus books](https://github.com/LiShuMing/cygnus/tree/main/books).
- `python/projects/py-email` moves to
  [Lyra email-digest](https://github.com/LiShuMing/lyra/tree/main/modules/email-digest).
- `python/projects/py-learn` moves to
  [Lyra daily-learning](https://github.com/LiShuMing/lyra/tree/main/modules/daily-learning).
- Calcite, RisingWave, Claude and Feynman books and all unrelated content/gitlinks
  are unchanged. Existing ignore rules stay to protect old local credentials/state.
- `python/projects/cron.sh` stays byte-for-byte unchanged. It is an unsupported
  machine-specific historical script with dangling PIA and email paths. Do not
  run it or install a schedule from it. No functional replacement scheduler is
  claimed; orchestration and live-state migration remain separate work in Carina.

## Explicit exclusions: retained in history, not imported

The 12 historical documents below contain unique project history/planning rather
than disposable duplicates. They are intentionally superseded in the maintained
modules but preserved at pinned source and backup commits. The generated HTML may
contain private mail; its body is neither reproduced nor republished here.
Removal from the active tree is recoverable through Git and is not secure erasure.

| Source path | Git blob | Reason |
| --- | --- | --- |
| `python/projects/py-email/CHANGELOG.md` | `78a644a0ed9ff2f1ac58782f2d8061e32a8f4be6` | Legacy operational notes, role/task instructions or superseded plan; excluded to avoid importing personal operational context and obsolete unsafe setup/reset guidance. Fresh module documentation replaces it. |
| `python/projects/py-email/CHANGE_LOGS.md` | `cbeb2adea60cba84a1e8bac9ff0ae328ea27fd22` | Legacy operational notes, role/task instructions or superseded plan; excluded to avoid importing personal operational context and obsolete unsafe setup/reset guidance. Fresh module documentation replaces it. |
| `python/projects/py-email/CLAUDE.md` | `7044162282d35c1424667d8cc1ade238407b18af` | Legacy operational notes, role/task instructions or superseded plan; excluded to avoid importing personal operational context and obsolete unsafe setup/reset guidance. Fresh module documentation replaces it. |
| `python/projects/py-email/CLAUDE_v1.md` | `8deea5b3912bea105804a553876ec2435597dab2` | Legacy operational notes, role/task instructions or superseded plan; excluded to avoid importing personal operational context and obsolete unsafe setup/reset guidance. Fresh module documentation replaces it. |
| `python/projects/py-email/ISSUES.md` | `2ceeea1485904f1ff902721ac66c9e7471538668` | Legacy operational notes, role/task instructions or superseded plan; excluded to avoid importing personal operational context and obsolete unsafe setup/reset guidance. Fresh module documentation replaces it. |
| `python/projects/py-email/ROLE.md` | `6c8b7d0113c973032f4f4b73fe096ae96236e2d3` | Legacy operational notes, role/task instructions or superseded plan; excluded to avoid importing personal operational context and obsolete unsafe setup/reset guidance. Fresh module documentation replaces it. |
| `python/projects/py-email/RULES.md` | `bb33e7399a5f10c67a8f1e315df63d1761f7be2b` | Legacy operational notes, role/task instructions or superseded plan; excluded to avoid importing personal operational context and obsolete unsafe setup/reset guidance. Fresh module documentation replaces it. |
| `python/projects/py-email/TODOS.md` | `423f29f1933915f55ee2ff2e24296a8606887715` | Legacy operational notes, role/task instructions or superseded plan; excluded to avoid importing personal operational context and obsolete unsafe setup/reset guidance. Fresh module documentation replaces it. |
| `python/projects/py-email/digest-2026-03-23.html` | `fd027b31ed1f62f0cf713c276e567669c7fad0da` | Generated dated email digest may contain private mail content; excluded, no replacement content imported. |
| `python/projects/py-email/docs/superpowers/plans/2026-03-24-email-inbox-mvp.md` | `26aecd90046c8a28ee82e05285ce610bc8d134ab` | Legacy operational notes, role/task instructions or superseded plan; excluded to avoid importing personal operational context and obsolete unsafe setup/reset guidance. Fresh module documentation replaces it. |
| `python/projects/py-email/docs/superpowers/specs/2026-03-24-email-inbox-mvp-design.md` | `1fd21dbe27bfa12852ea575925bff8a3421bbf71` | Legacy operational notes, role/task instructions or superseded plan; excluded to avoid importing personal operational context and obsolete unsafe setup/reset guidance. Fresh module documentation replaces it. |
| `python/projects/py-learn/CHANGES_LOG.md` | `717a87353999aedfc695cdf0a2e7665133da5bf5` | Historical operational/change report; replaced by the independently verified migration record, no source report contents copied. |
| `python/projects/py-learn/TASKS.md` | `1112ef282a6f891940c57b1c83fc828790bbe72a` | Historical project backlog/state, not executable behavior or evidence of current completion; no operational report copied. |

## Recovery

Before applying this candidate, refresh origin/main and the backup ref again;
reconcile any changed source or target snapshot rather than deleting changed files.
The backup branch `backup/pre-constellation-cleanup-2026-10-14` must continue to
point to `fd15e65059ff7d0d01ed48b6347cd75881fb4b36`.

To inspect a historical original without changing current files:

```sh
git show 7f32434e0fdea5e9d957fd806121b68554fa3272:<source-path>
```

To recover one selected original into a dedicated recovery branch, use
`git restore --source=fd15e65059ff7d0d01ed48b6347cd75881fb4b36 -- <source-path>`.
Do not restore generated private mail or credentials into a publishable tree.
To undo a subsequently merged cleanup as a whole, use `git revert <cleanup-commit>`
and review the resulting branch before publication. This candidate has no remote
cleanup commit yet. No local runtime databases, credentials or schedules are deleted.
