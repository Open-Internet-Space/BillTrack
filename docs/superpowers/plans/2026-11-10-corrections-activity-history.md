# Corrections and Activity History Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Superuser corrections with retained, searchable business history and safe payments/reminders.
**Architecture:** SQLite row triggers store allowlisted snapshots in the business transaction. Application contexts identify operations; existing Django Admin and API workflows enforce human reasons. An independent submission ledger protects mail, and shared payment mutation handling maintains bill status.
**Tech Stack:** Existing Django, DRF, SQLite and React; no new dependencies.
**Spec:** ../specs/2026-11-10-corrections-activity-history-design.md

## Global Constraints

- Canonical development repository: E:\BillTrack-Clean; execute in its isolated E:\BillTrack-Activity-History worktree.
- Preserve ordinary-user permissions, validation and account-security workflows.
- No live database writes or real email tests. Preserve separate migration chains.
- Exclude credentials/security values. Audit has no mutation or retention interface.

## Review Focus

- Bulk writes and SET_NULL cascades retain snapshots within the same transaction.
- Payment reallocations/deletions refresh all surviving affected bills.
- Deleted/edited history cannot release a protected reminder claim.
- Authentication/context reuse does not assign another user's identity.
- Import replacement and reused primary keys preserve distinct readable history.

### Task 1: Transactional audit storage

Files: models/activity.py, activity/{context,database}.py, apps.py, migrations/0004_activity_history.py; tests/test_activity.py.
Interfaces: operation(actor=None, source='background', reason=...) context manager; ActivityEntry immutable records; SQLite context functions and allowlisted triggers.
- [ ] Write and run failing tests for bulk/cascade snapshots, redaction, identity reuse, rollback and immutability.
- [ ] Implement triggers and connection lifecycle; run focused tests until green.
- [ ] Record results and commit.

### Task 2: Financial and mail protections

Files: models/payments.py, models/reminders.py, reminders/{service,admin}.py; tests/test_activity.py; migrations.
Interfaces: Payment queryset coordinates derived bill changes atomically; ReminderSubmission is private authoritative send state, linked to optional visible delivery.
- [ ] Write and run failing tests for bulk payment changes/deletions and reminder correction/deletion blocking.
- [ ] Implement shared recalculation, submission backfill/claims/outcomes/review; preserve preview and confirmation.
- [ ] Run financial/reminder tests and commit.

### Task 3: Correction workflows and Activity log

Files: activity/{admin,api,middleware}.py; existing model admins, views, imports; frontend/src/api.js; admin templates/navigation; tests/test_activity.py and frontend/src/api.test.js.
Interfaces: required human reason for edits/deletes/imports, shared operation context after authentication; read-only superuser ActivityEntry admin.
- [ ] Write and run failing permission/reason/confirmation/log tests.
- [ ] Add required reason inputs and server enforcement, cascade previews, Admin correction rights and activity filters/detail/history.
- [ ] Run backend/frontend suites; resolve regressions and commit.

### Task 4: Compatibility, documentation and deployment preparation

Files: historical migration compatibility patch, component-map.json/generated maps, administration/reminder/recovery/API docs, isolated migration verifier.
- [ ] Test clean canonical migration and historical-chain upgrade, schema parity/backfill, rollback and drift.
- [ ] Update documentation and prepare backed-up deployment instructions without deploying.
- [ ] Run full backend/frontend/helper checks and request independent whole-change review; fix material findings with regression tests.

## Execution ledger

User approved proceeding with the design. Execute continuously in this session.
Task status and evidence will be recorded below as work progresses.

- Tasks 1–3 implemented: initial RED tests reproduced missing audit, stale bulk bill statuses, duplicate reminder eligibility, missing reasons and inline deletion preview. Focused audit/financial/reminder tests GREEN. Full file-backed SQLite backend 256 passed; frontend 69 passed. Canonical upgrade/backfill and drift checks passed.
- Ruling: trusted model/maintenance writes without context are audited as unmanaged, instead of rejected; rejecting them would break existing security/bootstrap workflows. Interactive edits/imports still require explicit reasons. Cost: operator attribution for a custom script requires its explicit operation context; documented in ACTIVITY-HISTORY.md.
- Ruling: use disposable file-backed SQLite for full concurrency verification; shared-memory SQLite produces immediate table-lock errors absent the production file-lock waiting behavior. Test-only teardown removes/reinstalls guards before Django flush. No application purge API exists.
- Task 4 in progress: historical compatibility, docs and independent review.

- Independent whole-change review found one important issue: provider review could release an active sender. Fixed with OS-owned per-submission locks and attempt/status compare-and-swap; deterministic duplicate-send and stale-worker regressions RED→GREEN. 55 focused audit/reminder tests and full canonical 258 tests pass after the fix.
- Backfill timestamp regression RED→GREEN: both chains now retain original creation/update timestamps; isolated canonical/historical upgrades and feature schema parity pass.
- Historical application suite: 255 tests passed. The bare historical discovery additionally found an ignored old invoice-baseline artifact under outputs whose expected pre-cursor HTML is stale; application tests exclude generated artifacts. No production code was changed to satisfy it.
- Native Windows build handling: call react-scripts via node directly in the historical worktree because its ampersand-containing path breaks the npm Windows command shim. Dependencies unchanged.

- Task 4 complete: canonical 258 and historical 255 application backend tests passed; both frontend variants 69 tests and production builds passed; each helper suite 12 passed; both migration/backfill/feature-schema parity and drift/component checks passed. Historical frontend tested from an ASCII-path isolated source copy because Windows Jest path matching fails in the original ampersand-containing directory; included the real placeholder script used by that suite.
- Production preparation: verified online full data/config backup, before-source/runtime archives, compatible after-source/frontend packages, task XML, checksums and operations/recovery notes in a private folder outside Git. Production remains at f9870d7 and its original process/listeners. No source install, migration, task restart or real SMTP test performed.
- Final review: one important finding fixed with RED→GREEN regressions and a green full canonical suite; no deferred review findings. Work remains on feature/corrections-activity-history for review, without a merge/push/deployment.
