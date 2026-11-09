"""Verified online SQLite backup using Python's standard library."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = ('instance', 'media', 'estate_app/static', 'frontend/public/static')


def check_destination(root, destination):
    destination = Path(destination).expanduser()
    if not destination.is_absolute():
        raise ValueError('Choose an absolute path, for example D:/BillTrackBackups.')
    destination = destination.resolve()
    if not destination.is_dir():
        raise FileNotFoundError(f'Backup folder unavailable: {destination}. Create/connect it first.')
    if any(destination.is_relative_to(root / folder) for folder in FOLDERS):
        raise ValueError('Choose a folder outside instance, media and application asset folders.')
    return destination


def configure_backup(root, destination):
    root = Path(root).resolve()
    destination = check_destination(root, destination)
    with tempfile.TemporaryFile(dir=destination):
        pass
    config = root / 'instance/backup.json'
    if config.parent.is_symlink() or not config.parent.resolve().is_relative_to(root):
        raise ValueError('instance must be an ordinary folder inside the app directory.')
    config.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=config.parent, delete=False) as stream:
        temporary = Path(stream.name)
        json.dump({'destination': str(destination)}, stream, indent=2)
    try:
        os.replace(temporary, config)
    finally:
        temporary.unlink(missing_ok=True)
    return config


def create_backup(root, destination=None):
    root = Path(root).resolve()
    if destination is None:
        destination = json.loads((root / 'instance/backup.json').read_text(encoding='utf-8'))['destination']
    destination = check_destination(root, destination)
    for required in ('db.sqlite3', '.env'):
        if not (root / required).is_file():
            raise FileNotFoundError(f'Missing {required}; complete initial setup before backing up.')
    sources = [root / '.env']
    for folder in FOLDERS:
        if (root / folder).exists():
            sources.extend((root / folder).rglob('*'))
    for path in [root / 'db.sqlite3', *sources]:
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError(f'Backup sources must be ordinary files inside the app folder: {path}')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    target = destination / f'billtrack-backup-{stamp}-{uuid.uuid4().hex[:8]}.zip'
    with tempfile.TemporaryDirectory(prefix='.billtrack-backup-', dir=destination) as stage:
        snapshot = Path(stage) / 'db.sqlite3'
        with closing(sqlite3.connect((root / 'db.sqlite3').as_uri() + '?mode=ro', uri=True)) as source:
            with closing(sqlite3.connect(snapshot)) as output:
                source.backup(output)
                if output.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError('Database integrity check failed; backup was not published.')
        archive_path = Path(stage) / 'backup.zip'
        with zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(snapshot, 'db.sqlite3')
            for path in sources:
                if path.is_file():
                    archive.write(path, path.relative_to(root).as_posix())
            archive.writestr('backup-info.json', json.dumps({
                'format': 1, 'created_utc': datetime.now(timezone.utc).isoformat(),
                'database': 'db.sqlite3', 'settings': 'Parameters are in the database; secrets are in .env.',
            }, indent=2))
        with zipfile.ZipFile(archive_path) as archive:
            if archive.testzip() is not None:
                raise ValueError('Archive verification failed; backup was not published.')
        archive_path.chmod(0o600)
        os.replace(archive_path, target)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configure', action='store_true', help='Choose and save the backup folder.')
    parser.add_argument('--destination', help='Existing folder for one backup, or save it with --configure.')
    args = parser.parse_args()
    try:
        if args.configure:
            destination = args.destination or input('Full path to your existing backup folder: ').strip().strip('"')
            print(f'Saved backup configuration: {configure_backup(ROOT, destination)}')
            print('Set the daily time in Task Scheduler or the Linux timer; see docs/BACKUP-RESTORE.md.')
        else:
            print(f'Backup verified and completed: {create_backup(ROOT, args.destination)}')
    except (OSError, ValueError, KeyError, sqlite3.Error, zipfile.BadZipFile) as error:
        print(f'BACKUP FAILED: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
