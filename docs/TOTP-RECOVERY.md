# Personal authenticator recovery

Active approved accounts can enroll at /accounts/authenticator/ using current password and a confirming app code. Scan the locally generated QR or enter its key manually. Setup expires after ten minutes; the key is not redisplayed after confirmation. Replacement requires a trusted administrator/operator identity check.

Personal TOTP works without SMTP. Recovery accepts username or unique email, a current code and a strong new password. Five submissions per account every fifteen minutes span aliases and sessions; used counters cannot be replayed. Recovery revokes tokens and invalidates old sessions, without approving/enabling accounts. Keep device/server clocks accurate.

Seeds are recoverable secrets stored in private SQLite and backups. This is account recovery, not a second factor at normal sign-in. A separate [superuser emergency key](SUPERUSER-EMERGENCY-TOTP.md) can recover an approved account when personal recovery is unavailable.
