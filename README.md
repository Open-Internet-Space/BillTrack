# BillTrack

Superuser corrections and retained before/after snapshots: [Activity log](docs/ACTIVITY-HISTORY.md).

Every bill. Every payment. In view.

An [Open Internet](https://www.anopeninternet.eu.org/) Project, developed independently as a personal project for billing and estate management.

## Which folder is for what?

| Folder | What it is for |
| --- | --- |
| `E:\BillTrack-Clean` | The main source repository: make and test all new changes here. This is the version published to GitHub. |
| `E:\EstateManagement` | The live application the office uses every day. It holds the real records, uploads and private settings. Install tested updates here; do development in the source repository. |

The normal order is: **make a change → test it → publish the source to GitHub → install a compatible update in the office application**. Uploading code to GitHub does not update the office application automatically.

**Important:** the two copies have different database histories. Copying the whole source folder over the live folder can break the office application or overwrite private files. Follow the [setup and update guide](docs/SETUP.md).

## Start here

- [Understand the two folders and choose the right instructions](docs/SETUP.md).
- [Set up a new Windows copy](docs/SETUP-WINDOWS.md) or [a new Linux copy](docs/SETUP-LINUX.md).
- [Use or update the existing office application](docs/PRODUCTION-WINDOWS.md).
- [Set your organisation details and private settings](docs/PRIVATE-CONFIGURATION.md).
- [Find all user and technical guides](docs/README.md).

## What BillTrack does

BillTrack manages allottees, bills, receipts, payments, penalties and reports. It prints individual, bulk and consolidated invoices. It also includes account approval and recovery, private data export/import, backups and email tools.

A new installation starts without business records or a default account. Enter your organisation details in **Admin → System Settings** before printing. Uploaded logos and saved details belong to that installation; they are not part of the source published to GitHub.

## Email workflows

- [Manual email drafts](docs/EMAIL-DRAFTS.md): choose a saved template, fill in an allottee's details, edit the draft and copy it into your mailbox. This does not send mail.
- [SMTP reminders](docs/EMAIL-REMINDERS.md): choose a template and allottees, open **Preview selected emails**, check the recipients and message, then **Confirm and send**. Automatic sending is disabled.
- [Allotment descriptions](docs/LISTS-AND-FILTERS.md#distinguishing-multiple-allotments): distinguish separate allotments belonging to the same person.

Developers can use the [feature-to-file guide](docs/COMPONENT-MAP.md) to find code. Read [development checks](docs/DEVELOPMENT.md), [security](SECURITY.md) and [publication guidance](docs/PUBLICATION-REVIEW.md) before sharing changes. Keep databases, passwords, uploads, exports and backups outside GitHub. Publishing source does not make the application safe to host on the public internet.
