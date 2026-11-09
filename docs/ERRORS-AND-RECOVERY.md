# Errors and uncertain saves

Errors remain visible with retry/dismiss actions. Server failures provide a reference for local logs without reflecting request bodies, query values or exception arguments. Recovery/approval/configuration errors use controlled messages.

A timeout during a write does not prove failure. Inspect the current record before retrying; writes are not blindly replayed. If printing requests organisation setup, an administrator must complete local System Settings. Do not weaken host, CSRF, authentication or firewall checks to fix a URL error.
