# Changelog

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
