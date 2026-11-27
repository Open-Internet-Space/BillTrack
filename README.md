# BillTrack

Estate management, allotment-wise billing and staff guides. See the [changelog](CHANGELOG.md), [estate workflow](docs/ESTATE-WORKFLOW.md), and [extensions and security deposits tutorial](docs/EXTENSIONS-AND-SECURITY-DEPOSITS.md).

Superuser corrections and retained before/after snapshots: [Activity log](docs/ACTIVITY-HISTORY.md).

Every bill. Every payment. In view.

An [Open Internet](https://www.anopeninternet.eu.org/) Project, developed independently as a personal project for billing and estate management.

## Which folder is for what?

| Folder | What it is for |
| --- | --- |
| Development checkout | Clone or extract BillTrack into a folder you choose. Make and test source changes here. |
| Live installation | The folder used by the running service. It holds live records, uploads and private settings. Apply only updates tested against that installation's database history. |

These folders can be on any drive. Run commands from the folder containing `manage.py` unless a step specifies another location.

The normal order is: **make a change → test it → publish the source to GitHub → install a compatible update in the office application**. Uploading code to GitHub does not update the office application automatically.

**Important:** the historical EstateManagement installation uses a different database migration history from this repository. Confirm the lineage and protect the live database and private files before updating. Follow the [setup and update guide](docs/SETUP.md).

## Start here

- [Understand the two folders and choose the right instructions](docs/SETUP.md).
- [Set up a new Windows copy](docs/SETUP-WINDOWS.md) or [a new Linux copy](docs/SETUP-LINUX.md).
- [Use or update the existing office application](docs/PRODUCTION-WINDOWS.md).
- [Set your organisation details and private settings](docs/PRIVATE-CONFIGURATION.md).
- [Find all user and technical guides](docs/README.md).

## What BillTrack does

BillTrack manages allotments, expiry alerts, bills, receipts, payments, penalties and reports. The optional premises register covers shops, offices, canteens and other units. Use **Knowledge Base** in the sidebar for staff guides. BillTrack prints individual, bulk and consolidated invoices and extension fee demands. It also includes account approval and recovery, private data export/import, backups and email tools.

A new installation starts without business records or a default account. Enter your organisation details in **Admin → System Settings** before printing. Uploaded logos and saved details belong to that installation; they are not part of the source published to GitHub.

## Email workflows

- [Manual email drafts](docs/EMAIL-DRAFTS.md): choose a saved template, fill in an allottee's details, edit the draft and copy it into your mailbox. This does not send mail.
- [SMTP reminders](docs/EMAIL-REMINDERS.md): choose a template and allottees, open **Preview selected emails**, check the recipients and message, then **Confirm and send**. Automatic sending is disabled.
- [Allotment descriptions](docs/LISTS-AND-FILTERS.md#distinguishing-multiple-allotments): distinguish separate allotments belonging to the same person.

Developers can use the [feature-to-file guide](docs/COMPONENT-MAP.md) to find code. Read [development checks](docs/DEVELOPMENT.md), [security](SECURITY.md) and [publication guidance](docs/PUBLICATION-REVIEW.md) before sharing changes. Keep databases, passwords, uploads, exports and backups outside GitHub. Publishing source does not make the application safe to host on the public internet.
