# Use and maintain the office application

Find the live installation folder in **Task Scheduler → the existing BillTrack task → Actions → Start in**. It contains `manage.py`, live records, uploads and private settings. Its drive and path depend on the computer. Use a separate BillTrack checkout for development and testing.

## Everyday use

Open the office application's usual browser address and sign in. You do not need to run setup commands or open the source folder to use BillTrack.

The office application uses Waitress, a Python web server. A Windows scheduled task starts it using the live installation's own Python environment and `scripts/serve.py`. The development test server, `runserver`, is not the server for daily office use.

## Browser addresses and network access

- `http://127.0.0.1:8000` opens BillTrack on the server computer itself. On a different PC, `127.0.0.1` means that other PC, not the office server.
- Other office PCs use the server's configured office-network address.
- Tailscale access uses the server's configured private Tailscale address and an authorised device.

The exact network addresses and firewall rules are private installation settings. Do not guess them or copy settings from a development folder. `scripts/configure_network.ps1` checks configured Windows interfaces and firewall rules before enabling network listeners.

Office-network HTTP traffic is not encrypted. Keep access restricted. Publishing source to GitHub does not make the server safe to expose to the public internet.

## If the application will not open

1. Check that you are using the correct saved address and that the server computer is on.
2. Ask the administrator to check the existing BillTrack startup task in **Task Scheduler**.
3. Ask them to inspect `logs/server.log` inside the live folder.
4. Record the error or reference number. Keep passwords, recovery codes and real records out of shared screenshots and messages.

Do not rerun new-install commands or create a replacement database as a troubleshooting step.

## Restarting for maintenance

An administrator should arrange a short pause in office use before stopping the application.

1. Ask users to save their work and close any forms being edited.
2. Open **Task Scheduler** and select the existing task for the live installation. Record its name and settings privately.
3. **Disable** its repeating schedule before using **End** to stop it. Otherwise Windows may start it again during maintenance.
4. Perform the planned maintenance from an Administrator PowerShell window, using the live installation's own Python environment where required.
5. Re-enable and run the same task. Do not create a second competing server.
6. Check login, a normal read-only page and the required office-network access before users resume work.

Restarting does not require reinstalling the application or replacing its settings.

## Installing an update in the office

This is work for the developer and the administrator. A normal user should not copy source files into the live folder.

1. **Prepare and test in your development checkout.** Use made-up records and separate test files. Complete the [development checks](DEVELOPMENT.md).
2. **Publish the reviewed source to GitHub from that repository.** Check the selected files contain no private data. Publishing alone does not update the office.
3. **Prepare a compatible office update.** The historical EstateManagement database has a different migration history. Check the live installation's applied migrations and rehearse the compatible update on a protected copy. Preserve existing migration files and records.
4. **Write down the update and recovery steps.** Record the source version, changed files, any database changes, required packages and matching browser files. Test how to return to the previous application version while preserving current records. If data must be converted, test that separately before the live update.
5. **Arrange a maintenance break and make a verified backup.** Keep the live database, uploads, `.env`, local configuration, current source/browser files and startup-task settings. Store the recovery package privately. Follow [Backup and recovery](BACKUP-RESTORE.md).
6. **Stop the live application using the maintenance steps above.** Install only the prepared update. Preserve the live private files, Python environment and task configuration; apply only the database instructions tested for this installation.
7. **Restart and check.** Verify login, records and balances, affected screens, invoice/report output and the network addresses staff use. Make sure existing records, uploads and settings are still present. Do not send real reminder emails just to test a deployment.
8. **Resume office use after the checks pass.** If they fail, keep the application closed to users and follow the prepared recovery instructions.

There is no safe universal command here to copy the whole development folder over the live folder. The database differences make each update's compatibility checks necessary.

## Automatic startup for a new installation

The [new Windows setup](SETUP-WINDOWS.md) does not create a scheduled task or firewall rules. An administrator must review and configure those for that new copy, using its own Python path and application folder as the working directory. Do not change the existing office task while setting up a different copy.

## Returning to an earlier version

Use the private recovery instructions that match the installed version. Older application code may not understand newer database changes or account-security rules.

Do not restore an old database just to undo a code update: it can remove bills, payments and other work entered since the backup. Read [Backup and recovery](BACKUP-RESTORE.md) before attempting recovery.
