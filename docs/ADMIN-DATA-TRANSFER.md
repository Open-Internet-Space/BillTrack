# Private data export and import

Superusers can export or import version 2 business JSON. It includes shops, allotment terms, allottees, bills, payments, assessed charges, deposit movements, System Settings and the uploaded logo. Version 1 exports are supported for legacy records. Local users, passwords, account permissions, runtime credentials and email history stay with the installation.

Replace requires a review, explicit confirmation and reason. Merge adds missing records and preserves matches. Linked bills match by term and billing month/year. Unlinked bills match by allottee and billing month/year. Protected financial attribution requires the matching local usernames. A private safety export is saved before changes, and invalid relationships are rejected before a transaction can replace records.

Keep downloaded billtrack-data-*.json, before-import JSON and backups private and outside source control. Importing an unconfigured blank profile keeps printing blocked until an organisation name is entered.

Reusable email templates are excluded from business JSON. Default draft CC addresses are included in System Settings. Use a full database backup to preserve templates; merged emails are temporary and are not saved; see [email drafts](EMAIL-DRAFTS.md).

Allotment descriptions are included in exports. Older version-1 records without the description or default draft CC field import with blank values for those optional fields. Unknown fields and other missing required fields are still rejected.
