# Setup and updates: start here

This guide explains where work happens and how changes reach the office application.

## 1. Know the two folders

| | Development folder | Live office folder |
| --- | --- | --- |
| Location | `E:\BillTrack-Clean` | `E:\EstateManagement` |
| Purpose | Make and test changes to BillTrack | Run the application the office uses daily |
| Data | Use made-up test records | Real bills, payments, accounts and settings |
| GitHub | Publish source changes from here | Do not use this as the source for new development |
| Changes | Develop here first | Install tested, compatible updates here |

The development folder is the **canonical repository**. That simply means it is the main, authoritative copy of the source code. The live folder is a working installation with private information.

## 2. Choose what you want to do

| Your task | Where to go |
| --- | --- |
| Use the office application | Open its usual browser address. No setup commands are needed. |
| Make a code change | [Development and testing](DEVELOPMENT.md) |
| Install a tested update for the office | [Office operation and updates](PRODUCTION-WINDOWS.md#installing-an-update-in-the-office) |
| Set up a completely new copy on Windows | [Windows setup](SETUP-WINDOWS.md) |
| Set up a completely new copy on Linux | [Linux setup](SETUP-LINUX.md) |
| Change the organisation name, logo or invoice details | [Private settings](PRIVATE-CONFIGURATION.md) |
| Back up data or recover from a problem | [Backup and recovery](BACKUP-RESTORE.md) |

The new-copy instructions create a new database. They are not instructions for updating `E:\EstateManagement`.

## 3. Understand how an update travels

BillTrack databases on migration `0005_protected_submissions` can upgrade through estate migrations `0006` to `0017` after a verified backup. The office installation has a separate migration lineage and uses its separately tested release.


1. Make the change in `E:\BillTrack-Clean`.
2. Test it using made-up records and separate test files.
3. Publish the reviewed source from that repository to GitHub. Keep private files out.
4. Prepare an update that works with the live application's existing database.
5. Back up the live installation and arrange a short break in office use.
6. Install the tested update, restart the application and check that it works.

**GitHub stores source code. It does not automatically install that code in the office.**

## 4. Keep office information in the live installation

These files and folders belong to each installation, not to the shared source:

| Item | What it contains |
| --- | --- |
| `db.sqlite3` | Saved records, accounts and organisation settings |
| `media` | Uploaded files, including logos |
| `.env` | Private keys, email credentials and connection settings |
| `instance` | Local configuration, such as the backup destination |
| Backups and exports | Copies of private records and, for full backups, secrets |

A file beginning with a dot, such as `.env`, may be hidden by the file browser. Do not upload these private items to GitHub or replace them with development copies.

## 5. Why the database needs special care

A **migration** is an instruction that changes the database structure, such as adding a field. The clean source repository and the older office installation have different sets of these instructions.

That is why the source's fresh-install database instructions cannot simply be run over the office database. A developer must prepare and test an update using the office installation's existing migration history. The office's current records and uploaded files must survive the update.

## Words used in the guides

| Word | Plain meaning |
| --- | --- |
| Repository, or repo | The source files and their recorded change history |
| Commit | A saved version of source changes |
| Deploy | Install a tested update into the application people use |
| Frontend | The pages and controls you see in the browser |
| Backend | The Python application that reads and saves records |
| Build | Turn the browser source into files the application can serve |
| Rollback | Return to a previous application version after a problem |
| Virtual environment | A separate set of Python packages for one copy of the application |

If a command fails, stop at that step and keep the error text. Do not try the same command in the live folder to see whether it works there. Share error messages without passwords, private keys or real records.
