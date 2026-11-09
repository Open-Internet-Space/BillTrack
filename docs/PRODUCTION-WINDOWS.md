# Daily operation and network access

Waitress is started with the installation's Python and scripts/serve.py. It always provides loopback access on port8000. Optional LAN/Tailscale addresses are private .env values; configure exact hosts, CSRF origins and restricted firewall rules. scripts/configure_network.ps1 checks the supplied interface/range before enabling listeners. No real office IPs or firewall IDs are shipped.

Logs are local in logs/server.log. Review references/errors without sharing request bodies, passwords or recovery codes. To maintain a scheduled installation, disable its repeating task before ending it; run maintenance from an Administrator PowerShell, then re-enable/start the same task. Keep startup/account settings recorded privately.

This preparation does not install tasks, change firewall rules or alter an existing server. Choose task names/accounts deliberately; never run a task installer against another installation. For a backup/source rollback, preserve current database, uploads, credentials and local configuration. A future migration from another application's database requires a separate tested plan.

Office-LAN HTTP is unencrypted; source privacy is not internet deployment hardening. Keep access restricted and do not use Django runserver for daily operation.
