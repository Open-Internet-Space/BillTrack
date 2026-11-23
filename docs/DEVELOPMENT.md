# Development and testing

Clone [Open-Internet-Space/BillTrack](https://github.com/Open-Internet-Space/BillTrack) into a development folder of your choice. Use a separate working directory and environment for the live installation.

For an explanation of these roles, see [Setup and updates](SETUP.md). For first-time Python and browser setup, see [Windows setup](SETUP-WINDOWS.md) or [Linux setup](SETUP-LINUX.md).

## 1. Keep testing separate from office work

Use the development copy's own Python environment, `.env`, database, uploads and output folders. Use made-up accounts and records. Never run tests that write data against the office installation, and never use real mailboxes for automated mail tests.

On the same computer as the live server, use port 8001 for a temporary test server and leave the office port 8000 alone. The setup guides explain the corresponding private origin setting.

Use [the component map](COMPONENT-MAP.md) to find the files for the feature you are changing. Reuse the application's existing patterns.

## 2. Run the Python checks

Build and collect the frontend assets as shown below before running Django tests that render pages. Then open PowerShell in your development folder containing `manage.py`:

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test estate_app
.\.venv\Scripts\python.exe -m unittest discover -s scripts -p 'test_*.py'
.\.venv\Scripts\python.exe scripts/build_component_map.py --check
```

On Linux, replace `.\.venv\Scripts\python.exe` with `.venv/bin/python`.

| Check | What it tells you |
| --- | --- |
| `check` | Whether Django finds basic configuration problems |
| `makemigrations --check --dry-run` | Whether model changes are missing database migration files |
| `test estate_app` | Whether application tests pass using a separate test database |
| `unittest discover` | Whether helper-script tests pass |
| `build_component_map.py --check` | Whether generated code guides match their source registry |

Keep the `estate_app` test label: a broad test search can pick up old generated scripts in ignored output folders. Stop and fix failures before preparing a deployment.

## 3. Check the browser application

From the development root in PowerShell:

```powershell
Set-Location frontend
npm ci
npm test -- --watchAll=false --runInBand
$env:BUILD_PATH = '../frontend_build'
npm run build
Remove-Item Env:BUILD_PATH
Set-Location ..
.\.venv\Scripts\python.exe manage.py collectstatic --noinput
```

The tests check the browser code. The build produces the files used by the running application and regenerates the Knowledge Base from its selected Markdown guides. On Linux, use `BUILD_PATH=../frontend_build npm run build` instead of the PowerShell environment-variable steps.

If Windows npm wrappers fail because an installation path contains special characters, use a direct Node invocation of the installed `react-scripts` entry point. Do not change the office folder to work around a development-path error.

Manually check affected screens and outputs using made-up records. For email previews use fake or local-memory mail backends; do not send real mail from automated tests.

## 4. Keep organisation information out of source

Organisation details belong in **Admin → System Settings** and private uploaded media. Do not add real names, bank details, logos, credentials or real records to source, examples, test fixtures or migration files. `.env.example` must contain placeholders only.

Keep generated documents, databases, backups and logs ignored by Git. Before publishing, review selected changes and scan source/history for secrets and private identifiers. Review individual synthetic test findings rather than excluding whole test folders. See [publication guidance](PUBLICATION-REVIEW.md).

If code structure changes, update `docs/component-map.json`, then run:

```powershell
.\.venv\Scripts\python.exe scripts/build_component_map.py
```

This regenerates both feature-to-file guides. Run its `--check` command again afterward.

## 5. Prepare the office update separately

The clean repository starts with a fresh database structure. Its migration `0002_email_templates` and later migrations belong to that clean history; they do not replace the office installation's older history.

Never connect the clean initial schema to the live database or copy the development database into the office folder. Prepare a compatible update with the live migration chain and a private recovery package. Follow [Installing an update in the office](PRODUCTION-WINDOWS.md#installing-an-update-in-the-office).

Reusable email templates are saved in each installation's database; merged drafts are temporary. Test draft generation without sending mail. See [Email drafts](EMAIL-DRAFTS.md).
