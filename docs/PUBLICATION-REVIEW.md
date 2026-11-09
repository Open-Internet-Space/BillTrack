# Private clean repository preparation

This is a new, initially private BillTrack repository for fresh installations. It contains a reviewed source snapshot, generic documentation/branding, synthetic tests and a new initial schema. Old Git history, tags, issues, Actions logs, deployment archives, institutional images and operational narratives are not imported.

Organisation identity, bank/tax/signing details and private logos are configured only in local SQLite/media. Runtime credentials stay in .env. Saving configuration must not change tracked source. Exports and backups still contain private data and are not publishing artifacts.

Before publishing the prepared source, verify a fresh migration/install, configuration persistence, invoice print guards/formats, private export/restore and backup round trips; run tests/builds and secret/identifier/image-metadata scans. Document actual results separately in private working evidence. A pattern scan is not a guarantee against every unknown private value and is not a full application vulnerability audit.

The original repository and daily installation remain private and untouched. Their existing history is not cleaned by this preparation. The new repository is not a drop-in database upgrade, not publicly visible, and has no release/tag. A future public-distribution or live-migration decision is separate.
