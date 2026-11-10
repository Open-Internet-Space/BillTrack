# Historical EstateManagement compatibility

Use these two new migrations only after the historical
`0026_tenant_allotment_description`. Canonical BillTrack uses `0004`/`0005`;
never install both pairs or replace an existing migration chain.

Apply the reviewed feature source patch to an isolated historical checkout,
preserving unrelated privacy/configuration differences. Install the supplied
files as `estate_app/migrations/0027_activity_history.py` and
`0028_protected_submissions.py`. They require the new activity modules/models;
copying only migrations is insufficient.

Run full tests and migration drift checks, then from canonical development run:

```text
python scripts/verify_activity_migrations.py --historical-root <compatible-checkout>
```

The verifier creates disposable databases and synthetic reminder outcomes. It
does not copy/open installation data. It checks all six status backfills,
deleted-history retention, audit capture, integrity and feature schema parity.
Follow [recovery and deployment guidance](../../docs/ACTIVITY-HISTORY.md).
Never copy canonical Git metadata, environment, databases or institutional
defaults over the live setup.
