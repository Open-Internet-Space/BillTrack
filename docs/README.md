# BillTrack guides

**Start with [Setup and updates](SETUP.md).** It explains the two folders, how updates reach the office and which instructions apply to your task.

Superuser corrections and retained before/after snapshots: [Activity log](ACTIVITY-HISTORY.md).

Develop and test in a separate checkout. The live installation is the folder used by the running service and holds real records, uploads and private settings. Each computer can use different folders and drive letters.

## Set up or maintain the application

- [Windows setup](SETUP-WINDOWS.md): create a new copy with an empty database.
- [Linux setup](SETUP-LINUX.md): create a new copy on Linux.
- [Office operation and updates](PRODUCTION-WINDOWS.md): use, restart or update the live application.
- [Private settings](PRIVATE-CONFIGURATION.md): organisation details, logos and email credentials.
- [Backup and recovery](BACKUP-RESTORE.md): protect records and understand recovery limits.
- [Data export and import](ADMIN-DATA-TRANSFER.md): move business records using Admin.

## Use BillTrack

- [Estate staff workflow](ESTATE-WORKFLOW.md) and [estate API](ESTATE-API.md). The sidebar **Knowledge Base** lists the staff guides.
- [Changelog](../CHANGELOG.md).
- [Invoice settings](INVOICES-AND-SETTINGS.md), [receipt billing](RECEIPT-BILLING.md), [reports](REPORTS.md) and [lists and filters](LISTS-AND-FILTERS.md).
- [Manual email drafts](EMAIL-DRAFTS.md) and [email reminders](EMAIL-REMINDERS.md).
- [Accounts](EMAIL-ACCOUNTS.md), [personal authenticator recovery](TOTP-RECOVERY.md) and [superuser emergency recovery](SUPERUSER-EMERGENCY-TOTP.md).
- [Errors and recovery](ERRORS-AND-RECOVERY.md) and [Admin maintenance](ADMIN-MAINTENANCE.md).

## Change or publish the source

- [Development and testing](DEVELOPMENT.md).
- [Feature-to-file guide](COMPONENT-MAP.md): find the code for a screen or feature.
- [Private repository preparation and review](PUBLICATION-REVIEW.md).

The clean repository has a new database history. Its new-install commands are not an upgrade procedure for the existing office database. Updates for that installation must preserve its original migration history and private information.
