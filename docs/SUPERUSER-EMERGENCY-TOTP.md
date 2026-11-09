# Special superuser emergency TOTP

Private TOTP_RESET_SECRET is a separate emergency credential, not a user's personal authenticator. Its holder can recover any active approved account by choosing Superuser emergency TOTP on the recovery form, including an account with personal TOTP. It cannot approve or enable blocked accounts.

Admin password screens link to QR provisioning. Only a signed-in active superuser confirming their current password can reveal the configured key. QR generation is local; no third-party service receives it. Keep the key exclusively with trusted superusers. No working key is supplied in source.

An emergency code works once across all accounts, with twenty emergency attempts installation-wide per fifteen minutes plus per-account limits. HTTP429/Retry-After explain throttling. Changing the installation key requires provisioning the new key on trusted devices. A successful emergency password reset leaves the user's personal authenticator binding in place; replace a lost/compromised device separately.

Preserve private replay state during backup/restore. A database restoration can restore older counters. Keep clocks accurate and protect .env, SQLite and backups as authentication secrets.
