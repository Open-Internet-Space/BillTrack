# Set up a new Linux copy

These instructions create a **new installation with an empty database**. They do not update the Windows office installation. Read [Setup and updates](SETUP.md) first.

## 1. Prepare the computer and folder

You need Python 3.11 or later, Node.js 20 or later with npm, and the Pango/font libraries WeasyPrint needs to create PDFs. Package names depend on your Linux distribution; ask your administrator to install them if needed.

Download and extract the private repository into a new folder, or clone it. Open a terminal in the folder containing `manage.py`. Use a separate folder, database, uploads and settings for testing; do not use office files.

## 2. Install the Python packages

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

The `.venv` folder holds Python packages for this copy. If either command fails, resolve the error before continuing.

## 3. Create private settings

If this folder does not already have a `.env` file, create one:

```sh
cp -n .env.example .env
```

Open `.env` in a text editor. Generate a key for this installation:

```sh
.venv/bin/python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Paste it after `SECRET_KEY=` and keep `DEBUG=False`. Keep the local-only host settings initially. Leave optional network and email values blank until configured. The `WEASYPRINT_DLL_DIRECTORIES` example is for Windows; remove that line on Linux.

Keep `.env` private and do not replace an existing installation's key during routine updates.

## 4. Create the new database and your login

Run these only against this new copy's database:

```sh
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser
```

Follow the prompts. There is no default administrator password or sample business dataset. Password characters are not displayed while you type.

## 5. Prepare the browser files

```sh
cd frontend
npm ci
BUILD_PATH=../frontend_build npm run build
cd ..
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py check
```

Each command must finish successfully. These steps install browser packages, build the pages and collect their supporting files.

## 6. Start the application

For a separate new installation with port 8000 available:

```sh
.venv/bin/python scripts/serve.py
```

Open <http://127.0.0.1:8000> on that computer. The launcher uses Waitress and listens only on the local computer on Linux. Keep the terminal open; **Ctrl+C** stops a manually started server. Read `logs/server.log` if startup fails.

For temporary development alongside another server, use a separate port instead:

```sh
.venv/bin/python manage.py runserver 127.0.0.1:8001 --noreload
```

Before using port 8001, add `http://localhost:8001,http://127.0.0.1:8001` to this copy's `CSRF_TRUSTED_ORIGINS` list in `.env`. Open <http://127.0.0.1:8001>. This test server is not for daily office operation.

## 7. Finish setup

Open `/admin/` at the same address and sign in. Enter your organisation details in **System Settings** before printing. See [Private settings](PRIVATE-CONFIGURATION.md) and [Backups](BACKUP-RESTORE.md).

Ask an administrator to configure a Linux startup service, usually with systemd, if the installation must start automatically. Access from other computers needs its own network and, where appropriate, HTTPS setup. The Windows task and firewall scripts do not apply to Linux.

A complete fresh Linux installation has not been verified by the repository preparation checks. Confirm login, saving, PDF printing, restart and backup recovery on the actual machine before relying on it.
