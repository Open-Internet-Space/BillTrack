# SMTP payment reminders: preview, edit and confirm

Every financial reminder requires a superuser's editable preview and explicit confirmation. Automatic reminder sending is disabled. Signup/recovery codes and the non-financial mailbox setup test retain their existing workflows.

## Configure and test

Keep EMAIL_* and DEFAULT_FROM_EMAIL in the installation's private .env, restart BillTrack and use the setup test to your own mailbox. DEFAULT_FROM_EMAIL must contain a complete sender address, for example `"Office <mailbox@example.com>"`; a display name alone is invalid. Never share credentials in GitHub or screenshots.

## Edit templates and send

1. Open Admin → Email reminders → Edit saved email templates. Reuse the same named templates as manual email drafts. The placeholder picker explains each field and inserts it into Subject or Body. Save reusable wording with placeholders.
2. Return to Email reminders, choose an active template and select up to 25 eligible allottees. Click **Preview selected emails**. Nothing is sent or logged as a delivery yet.
3. Review the **From**, editable **To**, **CC**, **Subject** and **Body** for each email. Default CC addresses come from System Settings. Case-specific edits apply only to this send, not the saved template or allottee details.
4. Click **Confirm and send**. BillTrack sends exactly the reviewed fields after checking current balances, references, recipients, sender configuration and eligibility again. No invoice files are attached.

Previews are temporary and expire after one hour. Closing the page discards edits. If bills, payments, recipients or SMTP settings change, copy any wording you want to keep and prepare a new preview. Invalid fields retain your entered text for correction. Cancel returns to the list without sending.

## Eligibility and history

Receipt-based offsets remain due-1, due, due+1, due+7, due+14, due+26, due+41 and every fifteen days afterward, stopping three calendar months from confirmed receipt. Settled, inactive, missing-email, unconfirmed and expired records are skipped. Financial calculations and deadlines are unchanged.

At most one accepted reminder per allottee per day. Double-clicks, expired/tampered confirmations, stale balances and interrupted submissions cannot bypass the guards. An uncertain outcome needs review of provider activity before any fresh preview/retry. Do not retry blindly.

History records the actual primary recipient, eligible bills, attempts and SMTP status. It does not store case-specific draft text or CC lists; retain complete correspondence in the official mailbox. SMTP acceptance is not proof of inbox delivery. History and database backups are private.

## Scheduled tasks and command line

`python manage.py send_bill_reminders` still previews eligibility without sending. `--send` is rejected with instructions to use Admin. `--automatic` is a compatibility no-op that sends no mail, even if a historical database flag is enabled. Existing scheduled mail tasks can be disabled by an administrator; do not install new mail tasks for this workflow. The production server/startup task is unrelated and stays unchanged.

The old hardcoded email text file is retired. Edit saved templates in Admin; changing migration seed wording does not update existing saved templates. Full SQLite backups preserve templates and history; business-data JSON does not include them. See [manual email drafts](EMAIL-DRAFTS.md) and the [component map](COMPONENT-MAP.md).
