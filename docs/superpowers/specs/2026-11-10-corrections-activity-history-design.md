# Superuser corrections and activity history

Status: approved on 10 November 2026 and implemented on the corrections/activity-history
feature branch. Production deployment remains separate; see ACTIVITY-HISTORY.md.

## Intent and scope

Implement the supplied corrections/history specification in the canonical
`E:\BillTrack-Clean` repository (`Open-Internet-Space/BillTrack`). The current
EstateManagement worktree is the historical compatibility checkout, not the
canonical source. The daily installation is `E:\EstateManagement`.

Superusers can correct and delete allottees, bills, payments, email templates,
visible reminder history, accounts and configurable settings. Keep existing
validation, permissions for ordinary users, account-security workflows and
SMTP preview/confirmation requirements. Generated identifiers and derived
financial/security fields remain controlled by existing code.

Record business creates, edits and deletions from Admin, APIs, imports and
jobs, including bulk SQL and cascading effects. Preserve readable snapshots
after subjects and actors are deleted. The log supports investigation and
manual recovery; it does not promise automatic undo.

## Approaches

1. Admin hooks alone are small but omit APIs, fixture imports, jobs and bulk
   updates. They cannot satisfy the requested coverage.
2. Model save hooks/signals cover more paths but ordinary QuerySet updates
   bypass save signals. Wrapping every model/manager also needs special handling
   for Django accounts, relationship tables and fixture saves.
3. Recommended: SQLite row triggers for audited tables, with connection-bound
   operation context supplied by application workflows. Database changes and
   their audit inserts share a transaction, including bulk writes and cascades.
   Application services still perform validation and financial recalculation.

The third approach is the proposed builder choice. The existing project uses
SQLite exclusively. Supporting another database would require equivalent
trigger/context installation and its own verification; no new database support
or dependency is included. Confirm SQLite JSON and connection-function support
using the installed runtime before implementation.

## Audit storage and operation context

Add an ActivityEntry model with timestamp, actor ID and actor-name snapshot,
source, operation ID, action, reason, record type, record ID, stable business
identity and before/after JSON. Actor/subject references are snapshots, not
cascading foreign keys. Distinguish records whose integer primary keys are
reused after replacement imports by stable UUID or a recorded incarnation.
Account records need a durable incarnation because they currently lack UUIDs.

Use explicit field allowlists per business table. Include business settings,
account identity/approval/role changes and business foreign-key effects.
Include relevant permission/role relationship changes without serializing
authentication infrastructure. Capture nullifications caused by deleting a
user or allottee as changes to the affected business records.

Never capture passwords/hashes, OTP/challenge state, authenticator secrets,
recovery state, sessions, tokens, SMTP credentials or SMTP credential
fingerprints. Do not serialize request bodies, arbitrary model dictionaries,
exception objects, connection configuration or security tables. Sanitize
structured reminder snapshots by allowlisting their business keys. Arbitrary
user-written business text remains business data; do not copy credential
inputs into reason text or snapshots.
Suppress events when only excluded fields changed; password/hash or SMTP
verification changes must not produce misleading empty business edits.

Set actor/source/context after authentication, including DRF token
authentication; Django middleware alone cannot identify a token-authenticated
actor. Context is connection-bound, supports nesting and is cleared on errors
and connection reuse. Derived changes inherit the initiating operation.
Unauthenticated signup and scheduled operations use system sources and workflow
reasons, never a fabricated human actor. Implementation decision: legacy trusted
model/maintenance writes without context remain audited as unmanaged with a
diagnostic reason, preserving existing bootstrap/security workflows. Interactive
corrections and imports still require an explicit written reason. Custom trusted
scripts need an operation context for specific actor/reason attribution.
Bootstrap/data migrations use an explicit installation context. Avoid holding
transactions across unrelated requests or external network calls.

Guard audit entries against updates and deletions in normal database/application
use. Expose no API mutation route or Admin action, including for superusers.
Normal export/replace import excludes audit storage and submission protection;
replacement does not erase either. Keep them in full database backups. Provide
controlled test-database teardown without exposing an application purge path.
Direct database owners can remove guards or alter data; this is an acknowledged
limit, not external immutability.

## Corrections and reasons

Reuse Django Admin forms, validation and deletion collection. Add a required,
trimmed written reason for manual edits and deletions, including inline edits,
inline deletions, bulk actions and imports. A parent form reason covers its
inline changes under one operation. Reject blank reasons on the server before
any business write. Preserve reasons on validation errors.

Keep existing ordinary-user permissions unchanged. Existing ordinary-user edit
workflows also need a reason input where edits/deletions are already permitted;
this is a deliberate input-contract change, not a permission expansion. Update
frontend callers and tests together. API clients supply a reason with mutation
requests; reject absent reasons for manual corrections. Creates and explicitly
named automatic workflows receive a specific workflow reason unless the
operation is a correction/import requiring written justification. Do not let
user-controlled source/actor values impersonate a job.

Reuse the Admin deletion preview for one or multiple records, including
dependent business records and SET_NULL effects. Inline deletion and replace
imports must also show affected related records before confirmation. Confirm
against the current affected set inside the mutation transaction; changes since
preview require a refreshed preview. A reason alone is not deletion confirmation.
Expand correction rights only for superusers, preserving existing staff access.

Keep account password, OTP, authenticator, emergency recovery and token controls
on their existing protected routes. Do not make security internals editable in
the new correction forms. Preserve singleton settings behavior, with deletion
meaning reset to existing application defaults; verify lazy recreation is
audited and cannot bypass mail verification.

## Financial consistency

Payment.save already recalculates both old and new bills when allocation changes,
but the whole operation needs one transaction. Admin and API deletion currently
perform their own recalculation; consolidate this behavior so all supported
payment mutation paths, including bulk updates/deletes and imports, refresh
surviving affected bills exactly as needed. Preserve penalty settlement dates,
principal and penalty validation, and historical import monetary values.

Use the existing Bill.update_status calculation. Capture old and new bill IDs
before a mutation, recalculate after it and audit resulting bill updates within
the same transaction. Cascade deletion must not try to save a disappearing bill.
Bulk payment mutation paths need explicit coordination, beyond audit triggers:
triggers capture history but do not run Python financial calculations. Failures
in recalculation or audit insertion roll back the entire business operation.

## Protected reminder submission evidence

ReminderDelivery currently doubles as editable history and duplicate-send state.
Separate protected submission state before exposing corrections. A private
submission ledger retains original allottee UUID, send date, milestone/item
keys, submission state and review decisions independently of ReminderDelivery.
No cascading relationship may remove it with a delivery/allottee/account.

Backfill this ledger conservatively from existing history during migration.
Accepted and uncertain submissions continue to block resending after history
edits/deletion. Failed/skipped attempts retain the existing guarded retry rules.
Visible status/date/recipient/item changes never update protected submission
state. Existing explicit provider-review release remains a separate protected,
audited workflow; correcting a history row is not a release.
Identify provider-review releases by protected submission identity so the review
workflow remains usable after the visible history row has been deleted. Backfill
all four blocking states: preparing, sending, accepted and review, preserving
both daily allottee uniqueness and milestone/item blocking.

Claim attempts atomically using ledger uniqueness, recheck preview validity and
persist a protected sending state before SMTP. Never hold a database transaction
over SMTP. Store outcome plus audit entry in a subsequent transaction. If SMTP
accepts but outcome persistence fails, the committed sending state remains
blocking and requires provider review. Claim and visible-history writes share
their local transaction. Concurrent claims cannot submit twice. Editing/deleting
history performs no SMTP call and invalidates stale previews when applicable.

## Read-only Activity log

Use the existing Django Admin design and pagination. Add a superuser-only
Activity log with date, actor, record type and action filters and text search
over identity, reason and safe snapshot fields. Details show actor/source,
operation, reason, before/after values and record history, including deleted
records and deleted actors. Escape displayed values. No add, edit, delete,
bulk mutation, inline mutation or mutable REST endpoint is available.

This uses existing Admin UI rather than a separate React log application.

## Implementation reach

- Models/exports, application startup and database connection setup; audit and
  ledger migrations, including initial backfill and installation context.
- Admin common correction handling; allottees, bills/payment inline, payments,
  accounts/profile/group permissions, settings, templates and reminder history.
- API authentication and mutations, serializers, frontend edit/delete callers,
  bulk billing, receipt actions and approval workflows.
- Fixture-style import restoration, import preview/confirmation and backup;
  background commands, business saves triggered by reads and reminder services.
- New Activity log registration/templates/navigation and existing read-only
  maintenance links.
- Backend/frontend/helper tests and component registry/generated map.

Before implementation, inventory every business write in both repositories,
including raw fixture saves, QuerySet updates, relationship changes and lazy
settings creation. Do not treat auditing coverage as financial recalculation
coverage.

## Migrations and compatibility

Canonical schema currently ends at 0003_tenant_allotment_description. Add its
next migration without replacing existing migrations. The historical installation
ends at 0026_tenant_allotment_description and needs an equivalent migration
depending on that node. Prepare a separately reviewable compatibility patch in
the EstateManagement checkout; do not place both chains into one migration graph.
Keep model/table definitions and ledger backfill behavior equivalent.

Test clean installation and upgrades through each actual chain using isolated
databases, including existing accepted/uncertain reminders. Verify schema parity,
backfill counts, foreign-key checks and migration drift. No operation against
the live database is part of feature implementation/testing.

## Verification and rollout

Test superuser correction access; unchanged ordinary-user permissions; required
reasons on every manual mutation channel; missing-reason rollback; inline/bulk
and cascading deletion previews; snapshots of every affected business record;
account deletion/nullification; reused IDs; deleted actors; filters/search and
read-only enforcement. Exercise saves, raw import saves, bulk_create/update,
QuerySet.update/delete and nested rollback. Provoke audit insertion failure to
prove business writes roll back. Test context cleanup across sequential requests.

Test payment amounts, penalties, allocation across bills, individual/bulk/cascade
deletions, imports and recalculation failure. Test reminder history edits/deletes,
accepted/uncertain/failed attempts, stale previews, two competing claims, explicit
provider-review releases, and failure after SMTP acceptance. Use synthetic data
and a mocked mail backend; send no real email.

Seed unique sentinel secrets for every excluded security field and verify they
appear nowhere in audit storage or rendered details. Verify password/security
workflows continue working without leaking their values. Run existing backend,
frontend and helper checks and component-map/migration checks.

Update administration, API input changes, reminders, recovery, backup/import and
component-map documentation. State history starts on installation, has no expiry
and does not reconstruct earlier edits. Recovery uses readable snapshots with
existing validated entry workflows, not direct audit mutation or one-click undo.

Only after isolated validation, prepare a private deployment package with source
hashes, compatible migration, verified backup instructions, task pause/resume
steps and a reviewed recovery plan. Do not deploy to production during design
review. A pre-feature application may bypass new audit/duplicate-send guarantees,
so source-only rollback is not a safe default; preserve current data, audit and
ledger, and review compatibility before restart. Restoring an old database loses
subsequent changes and requires separate explicit approval.

## Deliberate limits

No external immutable storage, checkpoints, automatic retention expiry, audit
deletion interface, reconstructed earlier history, automatic financial undo or
new database engine support. Business text may contain sensitive personal data;
the log remains private to superusers and private backups.
