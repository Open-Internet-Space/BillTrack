import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from production_recovery import restore, verify
from serve import listen_addresses


class RecoveryTests(unittest.TestCase):
    def test_restore_preserves_new_ledger_and_media(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder); snapshot=base/'backup'; snapshot.mkdir(); target=base/'app'; target.mkdir()
            with zipfile.ZipFile(snapshot/'application.zip', 'w') as archive:
                archive.writestr('estate_project/settings.py', 'old configuration')
                archive.writestr('.env.example', 'public example settings')
                archive.writestr('desktop.ini', 'old Windows metadata')
                archive.writestr('frontend_build/index.html', 'old build')
            with zipfile.ZipFile(snapshot/'data.zip', 'w') as archive:
                archive.writestr('.env', 'old private settings')
                archive.writestr('db.sqlite3', 'old ledger')
            manifest={'database_archive':'data.zip', 'added_files':['new-check.py'], 'sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in snapshot.glob('*.zip')}}
            (snapshot/'manifest.json').write_text(json.dumps(manifest))
            (target/'db.sqlite3').write_text('new daily work')
            (target/'desktop.ini').write_text('existing protected metadata')
            (target/'media').mkdir(); (target/'media/logo.png').write_text('new logo')
            (target/'new-check.py').write_text('added by production update')
            restore(snapshot, target)
            self.assertFalse((target/'new-check.py').exists())
            self.assertEqual((target/'db.sqlite3').read_text(), 'new daily work')
            self.assertEqual((target/'desktop.ini').read_text(), 'existing protected metadata')
            self.assertEqual((target/'media/logo.png').read_text(), 'new logo')
            self.assertEqual((target/'estate_project/settings.py').read_text(), 'old configuration')
            self.assertEqual((target/'.env.example').read_text(), 'public example settings')
            self.assertEqual((target/'.env').read_text(), 'old private settings')
            (snapshot/'application.zip').write_bytes(b'corrupted')
            with self.assertRaises(ValueError): verify(snapshot)

    @patch('serve.os.name', 'nt')
    @patch.dict('os.environ', {'BILLTRACK_TAILSCALE_IP':'100.64.0.10','BILLTRACK_LAN_IP':''})
    @patch('serve.subprocess.run')
    def test_remote_listener_requires_successful_firewall_check(self, run):
        run.return_value.returncode=0
        self.assertEqual(listen_addresses(), ['127.0.0.1:8000','100.64.0.10:8000'])
        run.return_value.returncode=1; run.return_value.stderr='Firewall unavailable'
        self.assertEqual(listen_addresses(), ['127.0.0.1:8000'])
        run.side_effect=OSError('Tailscale unavailable')
        self.assertEqual(listen_addresses(), ['127.0.0.1:8000'])

    @patch('serve.os.name', 'nt')
    @patch.dict('os.environ', {'BILLTRACK_TAILSCALE_IP':'100.64.0.10','BILLTRACK_LAN_IP':'10.0.0.10'})
    @patch('serve.subprocess.run')
    def test_lan_remains_available_when_tailnet_check_fails(self, run):
        from types import SimpleNamespace
        run.side_effect=[SimpleNamespace(returncode=0),SimpleNamespace(returncode=1,stderr='Tailscale stopped')]
        self.assertEqual(listen_addresses(), ['127.0.0.1:8000','10.0.0.10:8000'])
