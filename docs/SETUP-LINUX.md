# Fresh Linux installation

Use Python3.11+, Node20+ and your distribution's WeasyPrint/Pango/font dependencies. Create .venv, install requirements.txt, copy .env.example to private .env and set a new SECRET_KEY with DEBUG=False. Run manage.py migrate and createsuperuser against a new empty database only.

In frontend run npm ci, then BUILD_PATH=../frontend_build npm run build. Run manage.py collectstatic --noinput, then .venv/bin/python scripts/serve.py. Linux starts loopback only with the current launcher. Additional network exposure needs a separately reviewed service/proxy configuration and HTTPS where appropriate.

Configure private System Settings before printing. Use a reviewed systemd unit for the installation account if autostart is needed, and configure backups separately. Windows-specific task/firewall scripts do not apply. No fresh Linux install is claimed as verified by this preparation.
