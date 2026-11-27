# Changelog

## 27 November 2026 — Allotments, extension fees and deposits

- Record and search allotment terms from the allottee register. Admin can switch the premises register and additional allotment fields on or off. The term form opens an approval and reason prompt for date exceptions. Term history supports reviewed deletion of records without protected links.
- Record a flat monthly rent or calculate it from area and rate. Maintain effective-dated rent revisions in the allottee's rent schedule.
- Find extension fee demands in **Bills**, print them using Invoice Format 2, and record receipts. A superuser can link a term previously entered as a separate original award and associate the existing fee with the extension.
- Consolidated printing groups monthly bills by allottee and draft status and keeps internal award and rate evidence out of invoices.
- Review deposits based on three times initial rent rounded upward to ₹100. Choose pre-order or post-order timing, record actual receipts, and record the allottee's decision to carry held security into a linked extension.
- Added admin switches for new signups, bill email communication and copying email drafts. The Gmail draft workflow supports configurable recipients and editable templates.
- Expanded the in-app Knowledge Base and GitHub guides with a searchable extensions and security deposits tutorial.

### Upgrade

Existing **BillTrack** installations on migration `0017_security_decision_operation` apply migrations `0018` through `0029`. Back up the database, rebuild the frontend, run migrations and collect static files before restarting. The historical EstateManagement installation has a separate migration history. See [setup and updates](docs/SETUP.md) and [backup and recovery](docs/BACKUP-RESTORE.md).

## 23 November 2026 — Estate management and Knowledge Base

### Added

- Searchable shop and allotment registers, including multiple shops per allottee, renewals, possession, handover and compliance records.
- Dashboard attention for allotments ending within 90 days, outstanding dues and other follow-up actions.
- Shop-wise bills, payment adjustments, assessed fees and fines, and separate security deposit tracking. The estate statement separates outstanding dues, cash received and deposits applied to obligations.
- Notice-based invoices with a seven-day deadline, confirmed email dispatch and simple interest on overdue principal. Holiday closures reduce rent by the actual number of closed days in each billing month.
- A sidebar Knowledge Base with 14 searchable staff guides and installation tutorials.

### Changed

- Existing bills and receipts retain their historical values. Review shop assignments and any policy conversion against office records.
- Invoice selections group by allottee and allotment term. Printed invoices show the applicable rent and staff-entered notes.
- Version 2 business exports include the estate records and financial links. The legacy receipt-policy workflow remains available for older bills.

### Upgrade

Back up and rehearse restoring the database before applying estate migrations 0006–0017. Rebuild and collect the frontend assets before restarting the application. After cutover, register shops and record terms from signed allotment letters. See the [estate workflow](docs/ESTATE-WORKFLOW.md), [backup guide](docs/BACKUP-RESTORE.md) and [setup and updates guide](docs/SETUP.md).
