# Private clean repository preparation

This is a new, initially private BillTrack repository for fresh installations. It contains a reviewed source snapshot, generic documentation/branding, synthetic tests and a new initial schema. Old Git history, tags, issues, Actions logs, deployment archives, institutional images and operational narratives are not imported.

Organisation identity, bank/tax/signing details and private logos are configured only in local SQLite/media. Runtime credentials stay in .env. Saving configuration must not change tracked source. Exports and backups still contain private data and are not publishing artifacts.

Before publishing the prepared source, verify a fresh migration/install, configuration persistence, invoice print guards/formats, private export/restore and backup round trips; run tests/builds and secret/identifier/image-metadata scans. Document actual results separately in private working evidence. A pattern scan is not a guarantee against every unknown private value and is not a full application vulnerability audit.

The original repository and daily installation remain private and untouched. Their existing history is not cleaned by this preparation. The new repository is not a drop-in database upgrade, not publicly visible, and has no release/tag. A future public-distribution or live-migration decision is separate.

## Preparation evidence

The isolated copy passed208 backend tests,60 frontend tests and12 helper tests, plus a production frontend build and fresh migration check. Synthetic Admin configuration survived a process restart without changing source; version1 export/import preserved the profile/logo, a verified SQLite backup restored its settings, and individual/consolidated/mixed invoice PDFs rendered. Institution-identifier and image-metadata checks passed before the initial commit. Five exact synthetic credential findings are individually reviewed; no test directory is excluded.

Windows and Linux operating-system installation procedures, physical printing/device scanning and public deployment were not certified by these checks. Python tests used an existing compatible dependency environment against an isolated new database; frontend packages were installed from the lockfile. No tasks, firewall rules or live installation were changed.
