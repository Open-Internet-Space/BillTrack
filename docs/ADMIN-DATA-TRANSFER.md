# Private data export and import

Superusers can export/import allottees, bills, payments and System Settings in version1 JSON. Export includes private institution/bank/tax/wording settings and an uploaded logo. Local users, passwords, account permissions, runtime credentials and email history are not business-export data.

Replace requires explicit confirmation; Merge adds missing records and preserves matches. A private safety export is saved before changes. Validation and transactions prevent partial import. Uploaded paths are never trusted; images are separately validated.

Keep downloaded billtrack-data-*.json, before-import JSON and all backups private and outside source control. Importing an unconfigured blank profile keeps printing blocked until an organisation name is entered. Export/import format and financial semantics remain unchanged.

Reusable email templates are excluded from business JSON. Default draft CC addresses are included in System Settings. Use a full database backup to preserve templates; merged emails are temporary and are not saved; see [email drafts](EMAIL-DRAFTS.md).

Allotment descriptions are included in exports. Older version-1 records without the description or default draft CC field import with blank values for those optional fields. Unknown fields and other missing required fields are still rejected.
