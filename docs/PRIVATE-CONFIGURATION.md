# Organisation details and private settings

Each copy of BillTrack has its own settings. Changing the development copy does not change the office copy. See [Setup and updates](SETUP.md) if you are unsure which one you have open.

## Change the organisation name, logo or invoice details

1. Open the correct application's browser address and sign in as an administrator.
2. Open **Admin → System Settings**.
3. Enter the organisation name, department, address and signing authority.
4. Check the tax registration, place of supply, bank/payee details, reference format, invoice wording and copy recipients that your office needs.
5. Upload the organisation's logo, save the settings and preview an invoice.

A new installation starts with a blank organisation profile. You must enter an organisation name before printing. If no logo is uploaded, BillTrack uses a generic image. Check saved billing rates for your own operation; changing branding does not change the application's calculation rules.

These details are stored in this copy's `db.sqlite3` database. Logos are stored under `media/invoice-branding`. Saving them does not edit source code or GitHub settings.

## What the .env file is for

`.env` is a private text file beside `manage.py`. It holds the installation's secret key, email login details and optional network addresses. It may be hidden in File Explorer.

It is not where you enter the organisation's name or invoice wording. Those belong in **System Settings**. `.env.example` is only a blank/example starting point; it must not contain working credentials.

Do not upload `.env` to GitHub, paste it into chat or replace it with another copy's file during an update. Keep the live installation's existing keys unless you are following a specific, reviewed key-change procedure.

## Change outgoing email settings

1. Identify the copy that sends the mail. For an office installation, check the application folder used by its existing startup task.
2. Have the administrator edit the `.env` beside that installation's `manage.py`.
3. Use the mail provider's required connection settings and credentials. Where required, use an app password rather than the normal account password.
4. Set `DEFAULT_FROM_EMAIL` to a complete email address, optionally with a display name, such as `Billing <billing@example.com>`.
5. Save the file and restart that installation using its existing startup task. Changes in the development `.env` do not affect the office server.
6. Follow [Email reminder setup and preview](EMAIL-REMINDERS.md) to check settings and review messages before sending.

## Protect saved settings and backups

Business exports include private organisation details and may include the logo. Full backups also include account secrets and `.env`. Share them only with authorised people and store them outside GitHub.

The database and backup ZIP files are not encrypted by BillTrack. Use restricted folder access and a protected backup destination. Git ignore rules reduce accidental uploads, but they do not make private files safe to publish manually.
