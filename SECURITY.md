# Security policy

Use [GitHub private vulnerability reporting](https://github.com/Open-Internet-Space/BillTrack/security/advisories/new) when available, or contact the repository owner privately. Include the BillTrack version and relevant details with synthetic records. Keep credentials, recovery codes, database files, and real customer data out of reports.

BillTrack v2.0.0 is intended for local or access-controlled private installations. **Do not update Django for this release.** The tested pin is `Django==4.2.11`. Django 4.2 is out of security support, so keep the live application off the public internet until a separately tested upgrade is available.

Production requires DEBUG=False and a private SECRET_KEY. Keep .env variants, SQLite/WAL files, media, logs, exports and backups out of source control. Organisation configuration is stored only in local SQLite/media. Backups contain bank/tax details, account secrets and recovery counters; filesystem permissions and private storage remain essential.

Email recovery and payment reminders require tested SMTP and explicit enablement. Personal TOTP works without SMTP. The special superuser emergency key can recover any active approved account; reveal requires a superuser and fresh password. Never distribute it to ordinary users. Recoveries revoke tokens and invalidate old sessions; global/personal replay counters and attempt limits must survive restarts.

Only synthetic credentials belong in tests. Before publication scan the staged tree and new history, inspect image metadata, and review releases/logs/artifacts separately. Public-distribution and dependency/security reviews are separate decisions. The original private installation/history are not imported or altered.
