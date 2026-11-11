# Validation

## Acceptance status

**Experimental source-only publication — narrowed gate approved 2026-11-11.**
The owner explicitly accepted deferring full installed acceptance after review of
the remaining failures. Required final-candidate checks are static, all root and
Cursor/hotfix helper units, unfiltered four-example source validation, all five
hotfix runtime regressions, publication inventory/export parity and independent
Gitleaks, on native macOS ARM64 with the exact public dependencies in
[compatibility](compatibility.md). Commit/fresh-clone tree and mode parity bind
those checks to publication; static CI must pass on the public commit.

**DEFERRED, NOT PASSED:** installed examples, installed authoring fixtures,
peer-helper identity execution, and a repeat full Linux/native matrix. Known
pinned-helper Linux `pidfd_open(EINVAL)` and macOS uncertain-ownership/uncertified
cleanup failures remain follow-up work. Local unpublished dependency repairs are
not release inputs. Historical Linux passes below are not final-byte claims.
No live providers or operational repositories are tested. Ticket delivery commits,
pushes and merges have real effects; test only with disposable repositories and
service projects under separate execution approval.

Automatic CI invokes only `scripts/check_static.py`: publication/privacy and local
links, source syntax, exact inventory/versions/references, Black, flake8,
ShellCheck, actionlint and Gitleaks. It never executes examples, unit/helper tests,
providers, plugin installation/builds or Transist.

## Complete maintainer gate (installed portions deferred)

Use isolated Python 3.11 with `PYTHONPATH=''` and `PYTHONNOUSERSITE=1`. Install
`requirements-dev.txt`; static binaries are ShellCheck 0.11.0, actionlint 1.7.12
and Gitleaks 8.30.0. Use a real Go toolchain for source/installed checks. Select
verified platform `TRANSIST_BIN` and matching `ADMIN_BIN`, the clean pinned
`PLUGINS_DIR`, and an existing canonical disposable `FIXTURE_BASE` outside source
and dependencies. On macOS use a sandbox-visible sibling `tmp` directory, not
system `/tmp`. On Linux use a dedicated native VM with root-owned exact source
copies for privileged namespace controllers; run ordinary units unprivileged.

Set `PEER_HELPER_SHA256` to the verified pinned plugin helper digest:
`fe7d6bc6279c07f080187b863f73906d2a20362894d1ff2e73d1d48546e81c52`.
From the exact exported repository run each command, capturing its exit separately:

```sh
python3 -B scripts/check_static.py
python3 -B -m unittest discover -s tests -p 'test_*.py'
python3 -B -m unittest discover -s examples/cursor_ticket_delivery/tests -p 'test_*.py'
python3 -B -m unittest discover -s examples/hotfix_ticket_delivery/tests -p 'test_*.py'
python3 -B scripts/check_examples.py --transist "$TRANSIST_BIN" \
  --plugins-dir "$PLUGINS_DIR" --home-base "$FIXTURE_BASE"
python3 -B scripts/check_peer_helper_identity.py --transist "$TRANSIST_BIN" \
  --plugins-dir "$PLUGINS_DIR" --helper-sha256 "$PEER_HELPER_SHA256" \
  --fixture-base "$FIXTURE_BASE"
python3 -B scripts/check_installed_examples.py --transist "$TRANSIST_BIN" \
  --admin-bin "$ADMIN_BIN" --plugins-dir "$PLUGINS_DIR" --fixture-base "$FIXTURE_BASE"
python3 -B examples/hotfix_ticket_delivery/tests/run_runtime_regressions.py \
  --transist "$TRANSIST_BIN" --shell-plugin "$PLUGINS_DIR/plugins/shell" \
  --fixture-base "$FIXTURE_BASE"
python3 -B scripts/check_public_snapshot.py --list
gitleaks dir --redact --no-banner "$EXPORT"
```

The unfiltered installed runner must complete four examples **and** three authoring
fixtures; inspect both results. Require all registered scenarios, zero required
skips, deterministic explanation comparisons and resource teardown. Restore normal
SIGINT handling before launching background children. Keep full evidence outside
public inventory. Fix source failures, regenerate the candidate, and repeat the
entire gate on both platforms; never weaken sandbox policy or assertions.

Source success is not live readiness or execution consent. Real ticket delivery
can mutate repositories, push, merge and affect service data; it needs separate
explicit authorization and operational prerequisites.

## Observed runtime 0.1.1 gate

Two complete serial attempts on each native platform retained separate command
exits against the same 125-file export. Both final attempts passed nine of ten
gates; the unfiltered installed suite failed. These are not release acceptance.

| Gate | macOS ARM64 | Linux ARM64 |
| --- | --- | --- |
| Static, publication inventory, independent secrets scan | Pass | Pass |
| Root / Cursor / hotfix helper tests | 123 / 45 / 14 pass | 123 / 45 / 14 pass |
| All four source checks, pinned peer-helper identity | Pass | Pass |
| Hotfix runtime regressions, including iteration exhaustion | 5/5 pass | 5/5 pass |
| Unfiltered installed examples and authoring fixtures | Incomplete | Incomplete |

Runtime 0.1.1 resolves the earlier bounded-loop exhaustion blocker: the contained
approval guard rejects exhaustion and publication never executes. Both actual CLI
introductory projections and delivery snapshot hashes remain unchanged. All homes
and recipes were newly created; no legacy routing metadata was retrofitted.

The selected public plugin helper remains exactly
`fe7d6bc6279c07f080187b863f73906d2a20362894d1ff2e73d1d48546e81c52`:

- macOS installed attempts fail with `fixture supervisor exited before owned
  cleanup`, unresolved Darwin ownership, and `cleanup_confirmed: false`. Failures
  occurred in Cursor validation and, on the repeat, the introductory edge fixture.
  This does not establish whether a fixture descendant or unrelated process caused
  the uncertainty; it does establish failed teardown acceptance.
- Linux installed attempts fail in `namespace_peers.py:561` with
  `os.pidfd_open(pid)` / `OSError: [Errno 22] Invalid argument`. Subsequent process
  observations are absent. The repeat passed Cursor reject, validation and success
  before failing in required isolation setup. The exact cause of the disappearing
  process observation remains unresolved; no error was suppressed.
- Initial Linux environment failures were separately retained: a preexisting
  regular file at `/dev/null` and a fixture base outside the approved temporary
  roots. After restoring the device and selecting approved `/tmp` storage, the
  complete serial gates still failed at the helper boundaries above.

The installed runner stopped before all four examples and three authoring fixtures
completed. No omitted fixture is counted as passing. Helper/teardown failures must
be resolved before claiming full installed acceptance. The narrowed publication
waiver does not convert failures into passes. Assertions and policy are unchanged.

## Historical runtime 0.1.0 validation

These failed receipts precede adoption of published runtime 0.1.1. Its bounded-loop
fix requires newly compiled recipes in fresh homes, not replay of legacy recipes.
The complete native gate must pass again before acceptance can be claimed.

The first exported snapshot passed static checks, 122 root tests, 45 Cursor helper
tests, 14 hotfix helper tests, peer-helper identity, publication checks and secrets
scans on both native platforms. All four source checks passed on macOS and, after
explicit prerequisite setup, Linux. These are partial results, not final acceptance.

- **Runtime loop exhaustion, both platforms:** hotfix runtime regressions pass
  4/5 scenarios. `iteration-limit` fails with
  `implementation module returned success without approval`. Persisted state shows
  the implementation module succeeded, `require_implementation_approval` was skipped,
  and the outer publication step failed later. The test requires the contained
  approval guard to fail and publication never to execute. Assertions and workflow
  definitions are unchanged. A separate four-step, control-only reproducer on
  both release binaries confirms that `until: 'false'` with `max_iters: 2`
  succeeds while skipping the mandatory post-loop successor. The `until: 'true'`
  control executes that successor. No plugin or delivery fixture is involved:
  compiled exit-edge predicate evaluation does not account for cap completion.
- **Intermittent peer cleanup failure, macOS:** the Cursor `validation` scenario
  failed with
  `fixture supervisor exited before owned cleanup`. The published plugin helper
  records unresolved Darwin process ownership and `cleanup_confirmed: false`.
  One isolated repeat failed; a later unchanged isolated run passed validation
  and certified cleanup, with no unresolved identities in any supervisor report.
  Earlier failed receipts remain failures. Their unresolved identities do not
  establish whether a fixture descendant or unrelated process caused the gap;
  a plugin defect is not proven. Full-gate teardown acceptance remains pending.

Workflow-side repairs resolve real-interpreter fixture shebangs and align the
hotfix runner's runtime/scratch prerequisites with the public baseline. Both Linux
canary runs then pass all five participants. Linux source-only prerequisite
discovery used explicit fail-on-execution provider sentinels; no provider was run.
This does not prove live provider installation or availability.

At that earlier checkpoint, unfiltered installed coverage, complete teardown,
final documented-export and committed-snapshot acceptance were incomplete. The
runtime/plugin dependencies were not modified and no test was weakened or omitted.
Current runtime 0.1.1 results and the remaining blockers are recorded above.
