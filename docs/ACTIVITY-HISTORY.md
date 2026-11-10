# Corrections and activity history

Superusers can correct/delete allottees, bills, payments, email templates,
visible reminder history, accounts and configurable settings in their existing
Admin pages. Validation, ordinary-user permissions, account recovery and SMTP
confirmation remain in their existing workflows. Internal invoice numbers,
UUIDs, derived financial values and security internals remain managed.

Edits/deletions require a written reason. A bill's reason covers its payment
inlines; deleting inline payments shows a separate effects confirmation. Single
and bulk deletion pages identify cascades and foreign keys that will be cleared.
Changed affected data invalidates confirmation. Application allottee deletion
still deactivates allottees with bills; superusers can use Admin for permanent
removal. Deleting settings resets them to application defaults when next needed;
deleting reminder settings removes SMTP verification, without enabling automation.

## Investigation and privacy

Open **Admin → Activity log**, also linked under Maintenance and modification.
Filter by date, actor name, record type or action; search identities, reasons
and safe snapshots. Entry details contain before/after values and a link to all
activity for that record. Existing model History links lead superusers here.
Incarnation identities keep reused integer IDs separate. Deleted records and
actors retain their snapshots. No add/edit/delete/bulk mutation or API mutation
interface is provided; database guards also protect activity updates/deletions
and original submission deletion.

History starts at installation; previous edits cannot be reconstructed. Existing
reminder outcomes are backfilled into protected submission storage without
fabricating earlier activity events. There is no expiry, purge interface,
external immutable storage or protection from owners who can alter the database
or remove guards.

Allowlisted snapshots exclude password hashes, OTPs, authenticator secrets,
challenge/recovery state, sessions, tokens, SMTP credentials and SMTP verification
fingerprints. Business text, recipients and financial details remain private;
never paste credentials into reasons or business fields. Logo snapshots retain
filenames, not file bytes; restore missing files from full backups.

## Payments and reminders

Payment saves, reallocation, bulk creation/update and deletion recalculate all
affected surviving bills using existing status/penalty calculations. Business
changes, derived changes and audit entries share a transaction. Imports retain
existing historical-value semantics and recalculate merged existing bills.

Original reminder submission state is separate from editable history. Changing
visible status/date/items/recipient or deleting history/allottees/accounts cannot
release accepted or uncertain sends. New sends retain reviewed To/CC/subject/body
in protected evidence/activity snapshots. Earlier message text is not rebuilt.
Actual sending still requires editable preview and explicit confirmation;
automatic sending remains disabled. SMTP acceptance does not prove inbox delivery.

The uncertain-submission section uses protected IDs, even after visible history
is deleted. Release requires a reason and explicit confirmation that provider
activity was checked and nothing was sent. Correcting history is never a release.
If SMTP accepts but outcome saving fails, the saved sending state blocks retry.
No database transaction spans an SMTP call.
Active workers hold an OS lock under private `instance/reminder-locks`; provider
review refuses release until the worker finishes or exits. Attempt/status checks
also stop stale workers from resuming a released claim. Keep the lock files;
deleting a lock file while a sender runs defeats coordination.

## API and maintenance contracts

PUT/PATCH/DELETE require nonblank `change_reason` (maximum 2000 characters),
or `X-Change-Reason`. The frontend prompts for it and sends JSON, supporting
non-ASCII reasons. Before DELETE, GET the record's `deletion-preview/`; show
`affected` and send its `confirmation` token with deletion. Tokens expire after
30 minutes and are invalid when affected data changes. Permissions are checked
again. Imports also require a reason; Replace confirms the current affected set.

SQLite triggers capture saves, raw fixture saves, bulk SQL, cascades and SET_NULL
changes within the business statement's transaction. Token authentication sets
the actor after validating the account. Trusted maintenance code should use
`operation(actor=..., source='background', reason='specific explanation')` from
`estate_app.activity.context`, inside its transaction. Nested contexts restore
their predecessor on errors. Legacy scripts without context remain visible as
**unmanaged**, with no human actor and a diagnostic reason; investigate against
maintenance/job records. Interactive edits/imports cannot use this fallback to
omit a reason. Use the Payment model/manager for financial corrections: raw SQL
receives auditing but does not run Python bill recalculation. Direct SQLite
clients without BillTrack's connection functions cannot write audited tables
normally. Other database engines are unsupported.

## Recovery and deployment

Use snapshots for manual recovery: check related records, then make a validated
correction with a reason referring to the original entry. There is no automatic
undo. Full database backups retain audit/submission evidence; business-data
export/import intentionally excludes it, and Replace preserves it. A business
export alone is not a full recovery backup.

Canonical migrations are `0004_activity_history` and `0005_protected_submissions`.
Historical installations use equivalent `0027`/`0028` after their existing `0026`;
see [compatibility instructions](../compatibility/estate-management/README.md).
Never replace historical migrations with canonical `0001` or fake the upgrade.

After isolated validation, prepare verified full backups and a reviewed package.
Finish saves; disable the server task before stopping it, and disable/stop any
separate reminder task. Install compatible source/migrations, build React,
collect static files, migrate and restart the existing task. Preserve environment,
database, uploads, firewall and scheduling. Verify sign-in, read-only lists,
invoices and Activity log; use isolated data for destructive/SMTP tests.
Implementation does not itself perform a production cutover.

Do not run older source-only rollback: old code can bypass send/payment safeguards
and new triggers require connection functions. Do not reverse these migrations
to undo the feature; doing so removes protected submission evidence. Prepare
compatible forward recovery or explicitly review full-backup restoration,
which loses work entered since that backup. Keep pre/post-update backups private.

Tests use disposable file-backed SQLite and mocked mail. Run the suites, drift
check, component-map check and `scripts/verify_activity_migrations.py`; add
`--historical-root <isolated-compatible-checkout>` to exercise both actual chains
and compare feature schemas. Generated databases/builds/reports stay outside Git.
