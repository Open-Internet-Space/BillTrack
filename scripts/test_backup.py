import sqlite3
from contextlib import closing
import tempfile
import unittest
import zipfile
from pathlib import Path

from backup import configure_backup, create_backup


class BackupTests(unittest.TestCase):
    def setUp(self):
        test_root = Path(__file__).resolve().parents[1] / 'outputs/backup-tests'
        test_root.mkdir(parents=True, exist_ok=True)
        self.workspace = tempfile.TemporaryDirectory(dir=test_root)
        self.addCleanup(self.workspace.cleanup)
        self.root = Path(self.workspace.name) / 'app'
        self.root.mkdir()
        self.destination = Path(self.workspace.name) / 'backup folder'
        self.destination.mkdir()
        (self.root / '.env').write_text('SECRET_KEY=fixture-only\n')
        for folder in ['media', 'estate_app/static', 'frontend/public/static']:
            path = self.root / folder
            path.mkdir(parents=True)
            (path / 'example.txt').write_text('asset')

    def test_live_wal_snapshot_includes_parameters_and_can_be_restored(self):
        with closing(sqlite3.connect(self.root / 'db.sqlite3')) as live:
            live.execute('PRAGMA journal_mode=WAL')
            live.execute('CREATE TABLE settings (value TEXT)')
            live.execute("INSERT INTO settings VALUES ('daily-parameter')")
            live.commit()
            configure_backup(self.root, self.destination)
            first = create_backup(self.root)
            second = create_backup(self.root)
            self.assertNotEqual(first, second)
            with zipfile.ZipFile(first) as archive:
                self.assertIsNone(archive.testzip())
                self.assertIn('instance/backup.json', archive.namelist())
                self.assertIn('media/example.txt', archive.namelist())
                self.assertIn('estate_app/static/example.txt', archive.namelist())
                self.assertEqual(archive.read('.env'), (self.root / '.env').read_bytes())
                restored = Path(self.workspace.name) / 'restored'
                archive.extractall(restored)
            with closing(sqlite3.connect(restored / 'db.sqlite3')) as snapshot:
                self.assertEqual(snapshot.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
                self.assertEqual(snapshot.execute('SELECT value FROM settings').fetchone()[0], 'daily-parameter')
            self.assertEqual(live.execute('SELECT COUNT(*) FROM settings').fetchone()[0], 1)

    def test_missing_database_does_not_create_an_empty_database_or_archive(self):
        with self.assertRaises(FileNotFoundError):
            create_backup(self.root, self.destination)
        self.assertFalse((self.root / 'db.sqlite3').exists())
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_missing_destination_has_no_silent_fallback(self):
        with self.assertRaises(FileNotFoundError):
            configure_backup(self.root, self.destination / 'unavailable')
        self.assertFalse((self.root / 'instance/backup.json').exists())

    def test_backup_destination_cannot_be_inside_files_being_archived(self):
        with self.assertRaises(ValueError):
            configure_backup(self.root, self.root / 'media')

    def test_missing_environment_is_an_error_not_a_partial_backup(self):
        with closing(sqlite3.connect(self.root / 'db.sqlite3')) as connection:
            connection.execute('CREATE TABLE example (id INTEGER)')
        (self.root / '.env').unlink()
        with self.assertRaises(FileNotFoundError):
            create_backup(self.root, self.destination)
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_configuration_cannot_escape_through_a_linked_instance_folder(self):
        outside = Path(self.workspace.name) / 'outside'
        outside.mkdir()
        try:
            (self.root / 'instance').symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest('Creating directory symlinks is not permitted on this host.')
        with self.assertRaises(ValueError):
            configure_backup(self.root, self.destination)
        self.assertFalse((outside / 'backup.json').exists())


if __name__ == '__main__':
    unittest.main()
