"""Exercise clean/upgrade migration paths on disposable SQLite files, never installation data."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile


PROBE = r'''
import datetime as dt
import json
import uuid
import django
django.setup()
from django.core.management import call_command
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor

before = '0026_tenant_allotment_description' if HISTORICAL else '0003_tenant_allotment_description'
call_command('migrate', 'estate_app', before, verbosity=0)
state = MigrationExecutor(connection).loader.project_state([('estate_app', before)]).apps
Delivery = state.get_model('estate_app', 'ReminderDelivery')
for status in ('preparing', 'sending', 'accepted', 'review', 'failed', 'skipped'):
    Delivery.objects.create(allottee_uuid=uuid.uuid4(), allottee_name='Synthetic '+status,
        send_date=dt.date(2026, 1, 1), recipient='synthetic@example.invalid',
        items=[{'key':status}], status=status)
call_command('migrate', verbosity=0)
from estate_app.models import ActivityEntry, ReminderSubmission, ReminderDelivery, Tenant
assert ReminderSubmission.objects.count() == 6
assert set(ReminderSubmission.objects.values_list('status', flat=True)) == {'preparing','sending','accepted','review','failed','skipped'}
assert not ActivityEntry.objects.exists(), 'Earlier activity must not be fabricated'
for delivery in ReminderDelivery.objects.all():
    original = ReminderSubmission.objects.get(delivery_id=delivery.pk)
    assert original.created_at == delivery.created_at and original.updated_at == delivery.updated_at, 'Original evidence timestamps changed during backfill'
ReminderDelivery.objects.all().delete()
assert ReminderSubmission.objects.count() == 6
assert ActivityEntry.objects.filter(record_type='estate_app.reminderdelivery',action='delete').count() == 6
with transaction.atomic():
    tenant = Tenant.objects.create(name='Synthetic migration probe', type='Shop')
    Tenant.objects.filter(pk=tenant.pk).update(name='Corrected probe')
    tenant.delete()
assert ActivityEntry.objects.filter(record_type='estate_app.tenant',action='delete').get().before['name'] == 'Corrected probe'
with connection.cursor() as cursor:
    cursor.execute('PRAGMA integrity_check')
    assert cursor.fetchone()[0] == 'ok'
    cursor.execute('PRAGMA foreign_key_check')
    assert not cursor.fetchall()
    cursor.execute("SELECT name,sql FROM sqlite_master WHERE type IN ('table','index','trigger') AND (name LIKE 'bt_%' OR tbl_name IN ('estate_app_activityentry','estate_app_remindersubmission')) ORDER BY name")
    schema = cursor.fetchall()
call_command('makemigrations', 'estate_app', check=True, dry_run=True, verbosity=0)
print(json.dumps(schema))
'''


def verify(root, historical=False):
    root = Path(root).resolve()
    with tempfile.TemporaryDirectory(prefix='billtrack-migration-') as directory:
        folder = Path(directory)
        (folder / 'probe_settings.py').write_text(
            "from estate_project.settings import *\n"
            f"DATABASES = {{'default': {{'ENGINE': 'django.db.backends.sqlite3', 'NAME': {str(folder / 'probe.sqlite3')!r}}}}}\n"
            "STATICFILES_DIRS = []\n", encoding='utf-8')
        env = {**os.environ, 'DEBUG': 'True', 'DJANGO_SETTINGS_MODULE': 'probe_settings',
               'PYTHONPATH': str(folder)+os.pathsep+str(root)}
        result = subprocess.run([sys.executable, '-c', f'HISTORICAL={historical!r}\n'+PROBE],
                                cwd=folder, env=env, text=True, capture_output=True)
        if result.returncode:
            raise RuntimeError(result.stdout+'\n'+result.stderr)
        import json
        return json.loads(result.stdout.strip().splitlines()[-1])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--historical-root', type=Path)
    args = parser.parse_args()
    primary_historical = (args.root / 'estate_app/migrations/0026_tenant_allotment_description.py').exists()
    canonical = verify(args.root, historical=primary_historical)
    print(('Historical' if primary_historical else 'Canonical')+' clean schema and upgrade/backfill: passed')
    if args.historical_root:
        historical = verify(args.historical_root, historical=True)
        assert canonical == historical, 'Audit/submission schema differs across migration chains'
        print('Historical upgrade/backfill and feature schema parity: passed')


if __name__ == '__main__':
    main()
