# Development and verification

Use an isolated environment, synthetic accounts and a separate database/media/port. Never run write tests against a daily installation. Install pinned dependencies and frontend packages, create a private test .env, then run Django tests, helper unittest discovery, frontend tests/build, migration drift and component-map checks.

```sh
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test estate_app
python -m unittest discover -s scripts -p "test_*.py"
python scripts/build_component_map.py --check
```

In frontend run npm test -- --watchAll=false --runInBand and build with BUILD_PATH=../frontend_build, then collect static files. Windows npm wrappers may require direct Node invocation of react-scripts when an installation path contains shell-special characters. Keep artifacts, databases, exports and logs ignored.

Organisation settings have one authority: local SystemSettings plus private media. Do not add institution-specific defaults to code, examples, fixtures, migrations or assets. .env.example must contain no working credential. After changing structure, update docs/component-map.json and regenerate both guides. Scan the entire new history and staged tree for secrets/private identifiers before publication; review synthetic scanner findings precisely rather than ignoring test directories.

This repository starts with a fresh schema, not inherited migration records. Do not connect it to an existing installation's database without a separate migration plan. No public hosting, visibility change or release is part of this preparation.

Manual template merging uses the additive 0002_email_templates migration in the clean-source lineage. Reusable templates are local database records; merged emails are temporary; generic seed wording contains no institutional data. Test generation without SMTP and keep snapshots/credentials outside Git. See [email draft behaviour and API](EMAIL-DRAFTS.md).

Use the maintained estate_app test label so old generated test scripts in ignored output folders are not discovered. SMTP preview tests use local-memory/fake SMTP backends, never live mailboxes. Deploying selected updates into a historical installation requires its compatible migration chain and private rollback package; never replace its database with the clean initial schema.
