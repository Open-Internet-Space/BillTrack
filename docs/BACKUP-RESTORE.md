# Private backups and restoration

scripts/backup.py and the installation-relative backup.bat configure an existing private destination, create an online SQLite/data backup and verify its archive. They do not automatically delete old folders. Legacy fixed-path/full-copy scripts are intentionally omitted. For full recovery also retain the matching source revision and either the matching frontend/static build or a reproducible rebuild procedure. Monitor space and test restoration separately.

Full backups include private database, media, configuration, account secrets and recovery history. Business JSON export includes organisation details and may include the logo. Neither belongs in GitHub. Do not restore an older ledger just to undo source changes, and do not restore a backup over a running server.

Preserve current data/credentials/uploads during code rollback and use version-matched instructions. prepare_account_rollback --apply quarantines signup-created accounts before returning to code without approval enforcement. Fresh schema0001 is not an upgrade path for an older installation; plan such a move separately.
