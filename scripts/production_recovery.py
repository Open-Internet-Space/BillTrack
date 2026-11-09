"""Verify or restore a pre-production application snapshot; never restore the ledger."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def verify(snapshot):
    snapshot = Path(snapshot).resolve()
    manifest = json.loads((snapshot / 'manifest.json').read_text(encoding='utf-8'))
    if 'application.zip' not in manifest['sha256'] or manifest['database_archive'] not in manifest['sha256']:
        raise ValueError('Incomplete recovery manifest')
    for name, digest in manifest['sha256'].items():
        if Path(name).name != name:
            raise ValueError('Invalid archive name')
        archive = snapshot / name
        if hashlib.sha256(archive.read_bytes()).hexdigest() != digest:
            raise ValueError('Recovery checksum mismatch: ' + name)
        with zipfile.ZipFile(archive) as stream:
            if stream.testzip() is not None:
                raise ValueError('Damaged recovery archive')
    return manifest


def restore(snapshot, target):
    snapshot, target = Path(snapshot).resolve(), Path(target).resolve()
    manifest = verify(snapshot)
    if target == Path(manifest.get('root', str(ROOT))).resolve():
        try:
            with socket.create_connection(('127.0.0.1', 8000), timeout=1):
                raise ValueError('Stop the BillTrack server on port 8000 before rollback.')
        except (ConnectionRefusedError, TimeoutError):
            pass
    added = []
    for name in manifest.get('added_files', []):
        path = (target / name).resolve()
        if not path.is_relative_to(target) or name.startswith(('.env', 'db.sqlite3', 'media/', 'backups/', 'instance/')) and name != '.env.example':
            raise ValueError('Unsafe added-file recovery path')
        added.append(path)
    with zipfile.ZipFile(snapshot / 'application.zip') as source:
        paths = []
        for member in source.infolist():
            if member.is_dir() or Path(member.filename).name.lower() == "desktop.ini":
                continue
            path = (target / member.filename).resolve()
            if (not path.is_relative_to(target) or member.filename != '.env.example' and member.filename.startswith(('.env', 'db.sqlite3', 'media/', 'backups/', 'instance/', '.git/'))):
                raise ValueError('Unsafe recovery member')
            paths.append((member, path))
        for member, path in paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(path.name + '.rollback-tmp')
            temporary.write_bytes(source.read(member))
            temporary.replace(path)
    with zipfile.ZipFile(snapshot / manifest['database_archive']) as data:
        temporary = target / '.env.rollback-tmp'
        temporary.write_bytes(data.read('.env'))
        temporary.replace(target / '.env')
    for path in added:
        path.unlink(missing_ok=True)
    print('Application and configuration restored. Database and media were NOT changed.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['verify', 'restore'])
    parser.add_argument('snapshot', type=Path)
    parser.add_argument('--target', type=Path, default=ROOT)
    args = parser.parse_args()
    if args.action == 'verify':
        verify(args.snapshot)
        print('Recovery archive checksums verified.')
    else:
        restore(args.snapshot, args.target)
