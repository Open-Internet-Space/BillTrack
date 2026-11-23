# Set up a new Windows copy

Use this page for a **new copy with an empty database**. If you only want to use the office application, open its usual browser address. To update it, use [Office operation and updates](PRODUCTION-WINDOWS.md).

Choose a new folder on an available drive. Keep it separate from any live BillTrack installation.

## 1. Check what you need

You need Python 3.11 or later, Node.js 20 or later, access to the private source repository and the native libraries WeasyPrint uses to create PDFs. Node.js includes the `npm` command used below. The Windows PDF library setup depends on your computer; get technical help if those libraries are missing.

Open **PowerShell** from the Start menu and check:

```powershell
python --version
node --version
npm --version
```

Each command should print a version. If a command is not recognised, install the missing tool and open a new PowerShell window before continuing.

## 2. Open the correct folder

Download the source ZIP for the branch or release you want from [the BillTrack repository](https://github.com/Open-Internet-Space/BillTrack), or clone it into a new folder. Open the extracted or cloned folder in File Explorer, right-click an empty area, and choose **Open in Terminal**. Use a PowerShell tab.

Run:

```powershell
Get-Location
Test-Path .\manage.py
```

Confirm that the displayed location is your chosen new folder and that the second command returns `True`. Use that folder for the commands below.

## 3. Install the Python packages

A virtual environment keeps this copy's Python packages separate from other applications.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Run these once when setting up the copy. If installation ends with an error, resolve it before continuing.

## 4. Create this copy's private settings

Check whether `.env` already exists:

```powershell
Test-Path .env
```

If it shows `False`, create it:

```powershell
Copy-Item .env.example .env
```

If it shows `True`, keep the existing file and review it; do not overwrite its secrets. Open it in Notepad:

```powershell
notepad .env
```

For a new copy, generate its own random key:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(50))"
```

Paste the result after `SECRET_KEY=` in `.env`. Keep it private. Keep `DEBUG=False`, and leave the local-only host settings from `.env.example` for now. Leave optional email and network settings blank until you need them. If WeasyPrint needs a DLL search folder, set `WEASYPRINT_DLL_DIRECTORIES` to the actual library folder on this computer. This setting is commented out in `.env.example`.

If the office application also runs on this computer, add `http://localhost:8001,http://127.0.0.1:8001` to the comma-separated `CSRF_TRUSTED_ORIGINS` list in this development copy's `.env`. Port 8001 keeps the test copy separate from the office application on port 8000.

Save and close Notepad. Do not copy the office `.env`, database or uploads into this copy.

## 5. Create the new database and administrator account

**Run this only for the new copy, using its own database.** The `migrate` command prepares its database tables; it is not an office upgrade procedure.

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
```

Follow the prompts to choose your administrator username and password. Nothing appears while you type a password; that is normal. There is no default login or sample business data.

## 6. Prepare the browser files

From the folder containing `manage.py`, run:

```powershell
Set-Location frontend
npm ci
$env:BUILD_PATH = '../frontend_build'
npm run build
Remove-Item Env:BUILD_PATH
Set-Location ..
.\.venv\Scripts\python.exe manage.py collectstatic --noinput
.\.venv\Scripts\python.exe manage.py check
```

`npm ci` installs the listed browser packages. The build prepares the pages, and `collectstatic` gathers the files needed to display them. Wait for each command to finish successfully.

## 7. Start the correct type of copy

**Development on a computer already running the office application:**

```powershell
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8001 --noreload
```

Open <http://127.0.0.1:8001>. This temporary test server is only for development. Press **Ctrl+C** in its PowerShell window to stop it. Do not run `scripts/serve.py` or `start_billtrack.bat` for this test copy while the office server uses port 8000.

**A separate new installation, with port 8000 available:**

```powershell
.\.venv\Scripts\python.exe scripts/serve.py
```

Open <http://127.0.0.1:8000>. This uses Waitress, the server intended for daily operation. Keep the window open while using it; **Ctrl+C** stops a manually started server. Server messages are saved in `logs/server.log`.

## 8. Enter your organisation details

Open `/admin/` at the same browser address and sign in with the administrator account you created. Go to **System Settings**, enter your organisation details and upload your logo. An organisation name is required before printing. See [Private settings](PRIVATE-CONFIGURATION.md).

If financial actions require the application's Admin role, set that role in the administrator's user profile. Test with made-up records first, including an invoice PDF.

## 9. Before relying on the new installation

Configure [backups](BACKUP-RESTORE.md). A developer or administrator should set up automatic startup and any office-network access for this copy, following [daily operation](PRODUCTION-WINDOWS.md). These commands do not create a Windows startup task or change firewall rules.

## If something goes wrong

| What you see | What to check |
| --- | --- |
| GitHub shows 404 | Sign in with an account that has access to the private repository. |
| A command is not recognised | Check the required tool is installed, then reopen PowerShell. |
| `manage.py` cannot be found | Return to the chosen application folder. |
| PDF library errors | Check the Windows WeasyPrint libraries and the path in `.env`. |
| Port already in use | Keep the office server running; use port 8001 for development. |
| A submitted form is rejected on port 8001 | Check this copy's `CSRF_TRUSTED_ORIGINS` includes its exact port-8001 address, then restart the test server. |
| The server fails to start | Read the error or `logs/server.log`; do not change the live copy to fix a test-copy error. |
