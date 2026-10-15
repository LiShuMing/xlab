# Consolidated repository cleanup

Base: xlab `bf3e2ed45c12cc551fd44ef3cb89366970cd92ba`.
One reviewable proposal covers repository hygiene. It does not authorize a push,
merge, live service operation, credential change or real-state migration.

## Legacy scheduler

`python/projects/cron.sh` is removed without a replacement stub. Its old
implementation is recoverable at the base commit (Git blob
`5d9e779b2e63295a56d120b4cd63ee6489c135c9`). It depended on retired PIA/email
paths and machine-specific setup. No installed system crontab or scheduler has
been inspected or changed. Any old scheduled invocation of that path will fail
with a missing-file error until its owner removes or replaces the schedule.
No sync, authentication, network calls, live-state transfer or scheduler changes
were performed by this cleanup.

Product intelligence is maintained in [Carina](https://github.com/LiShuMing/carina/tree/main/modules/product-intelligence),
and email ingestion in [Lyra](https://github.com/LiShuMing/lyra/tree/main/modules/email-digest).
These destinations are ownership routes, not automatic cron replacements.

## Retention and remaining gates

See [project classification](retained-projects.md). Unmigrated code, held books,
privacy exclusions, ignored/runtime files and the two pinned gitlinks are not
removed. Previously accepted Codex/Linux/email/learning source retirement is
already part of the base, not a new deletion in this proposal.

Calcite/RisingWave source retirement is pending target-main acceptance and exact
per-file mappings. If accepted, incorporate it into this same xlab proposal.
Claude Code/Feynman stay held. Do not fabricate acceptance or delete first.

The old [draft PR #20](https://github.com/LiShuMing/xlab/pull/20) contains obsolete
pre-acceptance status. Reconcile or close it separately with permission; do not
merge it blindly. This local proposal has not changed that PR.

## Validation boundaries

Run the offline repository test suite, shell syntax checks, whitespace checks,
and full tree-delta verification. Verify the two gitlinks and every unchanged
source entry. A repository-health result does not certify optional/native builds.
Dependency review must retain evidence of unresolved build consumers and may not
silence failures simply to make the healthcheck green.

## Dependency declaration decisions

The [69-row inventory](dependency-declarations.json) preserves every original
section/path/URL and the two pins. 29 orphan declaration blocks move out of
`.gitmodules`; 38 unresolved orphans remain visible to healthcheck and CI.
Four direct legacy CMake inputs (glog, abseil-cpp, fmt, folly), one manual
bootstrap input (fast_float), and 33 unknown-intent references need further
ownership/build decisions. No source code or package consumer is removed.
