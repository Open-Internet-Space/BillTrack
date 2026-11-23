# Backups and recovery

Run the backup command from the application folder containing the database you need to protect. To protect office records, use the live installation folder and its own Python environment.

## What needs protecting?

| Item | Why it matters |
| --- | --- |
| Database | Bills, payments, accounts, organisation details and saved email templates |
| Uploaded files | Logos and other private uploads |
| `.env` and local configuration | Keys, email credentials, connection settings and backup destination |
| Matching application version and browser files | Needed to run or rebuild the application that understands the saved database |
| Startup-task settings | Needed to restart the correct office installation after recovery |

The standard `scripts/backup.py` tool saves the database, `.env` and supported local data/asset folders. It checks database integrity and the ZIP archive. It does **not** save the whole source repository, Python environment, every generated browser file or Windows task. Keep the matching source version and browser build, or tested rebuild instructions, separately in the private recovery package.

## Set up a backup destination for a new copy

Create a private backup folder in a location you can write to, preferably on a separate drive. Open PowerShell in the installation folder containing `manage.py` and run:

```powershell
.\.venv\Scripts\python.exe scripts/backup.py --configure
```

At the prompt, enter the full path of the folder you created. The tool saves the destination in `instance/backup.json`. Automatic scheduling is configured separately. On Linux run `.venv/bin/python scripts/backup.py --configure` and enter the absolute path to your backup folder.

The existing office installation may already have a configured backup task and Python environment. Check its private operating instructions before changing either. These new-copy commands are not instructions to reconfigure the live office backup.

## Make and check a backup

From the configured new installation's folder:

```powershell
.\.venv\Scripts\python.exe scripts/backup.py
```

A successful run prints `Backup verified and completed:` followed by the ZIP path. A failure prints `BACKUP FAILED:`; do not treat that as a completed backup. The installation's `backup.bat` is another entry point to the same backup tool.

The tool can take a database backup while the application is running. For a coordinated pre-update recovery package, ask users to stop editing and follow the maintenance plan so uploaded files and other saved files remain consistent too.

Keep a protected copy away from the application drive, check available space and arrange an automatic schedule with the administrator if needed. The tool does not delete old backups automatically.

## Test recovery before you need it

An archive check cannot prove that you can restore the whole application. Ask the developer or administrator to rehearse recovery in a separate, protected folder using the matching application version. Confirm that login, saved records, uploaded files and required outputs work. Keep private rehearsal data outside the source repository and do not send reminder emails during the test.

Do not test recovery over the running office application.

## If an update fails

Use the private recovery steps prepared for that exact update. Returning to earlier code is called a **rollback**. It normally needs to preserve the current database, uploads and private settings.

**Do not restore an old database just to undo code changes.** That can erase bills, payments or account changes entered after the backup. Never restore files over a running server.

The office installation and clean source have different database migration histories. Do not replace the office database or its migrations with the clean `0001_initial` schema. A full move between those histories requires a separate tested plan.

Older code can also have different account-security behaviour. If returning to code without signup approval, a developer must review the documented `prepare_account_rollback --apply` step, which quarantines signup-created accounts. Do not run it as a routine backup command.

## Backups and business exports are different

A business JSON export is for transferring supported business data; it is not a complete application backup. Saved email templates are included in full database backups but omitted from business JSON exports. Default CC addresses are part of exported System Settings. Merged draft emails are temporary and are not saved. See [Data export/import](ADMIN-DATA-TRANSFER.md) and [Email drafts](EMAIL-DRAFTS.md).

Full backups contain private records, configuration and account secrets. They are not encrypted by the backup tool. Restrict access, protect offsite copies and never put backups or exports on GitHub.
