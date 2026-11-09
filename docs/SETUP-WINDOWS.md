# Fresh Windows installation

For isolated development testing on a machine already running another instance, use a separate database/media and `python manage.py runserver 127.0.0.1:8001`; never use runserver for daily production. The production scripts/serve.py launcher binds port8000 and must not be started on that machine during this preparation. Never point this fresh schema at an existing production database. Install Python3.11+, Node20+ and the native libraries needed by WeasyPrint for your system. Native-library setup is platform-specific and must be verified locally.

Download the private repository source ZIP or clone the master branch into a new directory. Do not reuse an old installation directory.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit the private .env. Generate a fresh long SECRET_KEY with Python secrets.token_urlsafe(50), keep DEBUG=False, and retain only the hosts/origins you actually use. Do not copy a real key into documentation or chat.

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
```

In frontend run npm ci and npm run build with BUILD_PATH=../frontend_build. Then run manage.py collectstatic --noinput and python scripts/serve.py using the virtual environment. Open http://127.0.0.1:8000. No default account/password or sample business data is created.

In Admin configure System Settings and upload your private logo before printing. Set the superuser profile role to Admin if financial actions require that app role. For automatic start, create a reviewed Windows task for scripts/serve.py with this installation as its working directory. Do not modify another installation's task or firewall. See [operation](PRODUCTION-WINDOWS.md) and [backup](BACKUP-RESTORE.md).
