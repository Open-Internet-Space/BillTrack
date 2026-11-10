# BillTrack

Every bill. Every payment. In view.

An [Open Internet](https://www.anopeninternet.eu.org/) Project, developed independently as a personal project for configurable billing and estate-management workflows.

This private clean source repository is for **fresh installations only**. It contains no organisation profile, private logo or previous installation history. Do not apply its new initial schema to an existing database.

## Start here

[Documentation index](docs/README.md) · [Windows setup](docs/SETUP-WINDOWS.md) · [Linux setup](docs/SETUP-LINUX.md) · [Private configuration](docs/PRIVATE-CONFIGURATION.md)

Configure organisation name, address, signing authority, GST registration, bank/payee details and invoice wording in **Admin → System Settings**. Values stay in local ignored SQLite; logos stay in private media. No .env organisation override or tracked configuration file is written. Printing requires an organisation name. Runtime keys and SMTP settings belong only in private .env.

Features include allottees, single/bulk/consolidated invoices, receipts, principal/penalty payments, reports, private export/import/backups, approved signup, email OTP/personal TOTP recovery, special superuser emergency recovery, SMTP reminders with mandatory editable previews and a searchable modification map.

Use [the feature-to-file guide](docs/COMPONENT-MAP.md) to modify components. See [security](SECURITY.md) and [private-repository preparation](docs/PUBLICATION-REVIEW.md). Dependency updates and public internet hosting need separate review. No default account or business dataset is supplied.

Selected features have also been deployed to the existing daily application through a separately validated compatibility build. That deployment preserves its original database/migration history and startup configuration; this clean source remains fresh-install only. Version-matched recovery files stay in private deployment backups. No release or tag is created. Keep downloaded exports, backups and generated documents outside Git.

Manual vendor correspondence: [merge saved templates and copy temporary email drafts](docs/EMAIL-DRAFTS.md). No mail is sent by the draft workflow.

## Email workflows

- [Manual email drafts](docs/EMAIL-DRAFTS.md): choose a saved template, merge an allottee's details, edit and copy into your mailbox. Draft emails are temporary.
- [SMTP reminders](docs/EMAIL-REMINDERS.md): select a template and eligible allottees, open **Preview selected emails**, review/edit To, CC, Subject and Body, then **Confirm and send**. Automatic/direct sending is disabled.
- [Allotment descriptions](docs/LISTS-AND-FILTERS.md#distinguishing-multiple-allotments): optional descriptions distinguish separate allotments belonging to the same person.

Admin template editing includes a labelled placeholder picker. The sign-in page offers separately spaced, touch-friendly signup and recovery links. See the [modification map](docs/COMPONENT-MAP.md) for the related code blocks.
