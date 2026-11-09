import json
from pathlib import Path
from tempfile import TemporaryDirectory
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from estate_app.maintenance import rollback_catalog

@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class MaintenanceTests(TestCase):
 def setUp(self):
  self.user=User.objects.create_superuser('maintenance-admin','admin@example.invalid','test-password')
  self.client.force_login(self.user)
 def test_both_guides_are_read_only_and_superuser_only(self):
  for url in ['/admin/rollbacks/','/admin/modification-guide/']:
   self.assertEqual(self.client.get(url).status_code,200)
   self.assertEqual(self.client.post(url,{}).status_code,405)
  self.user.is_superuser=False;self.user.save()
  for url in ['/admin/rollbacks/','/admin/modification-guide/']:
   self.assertEqual(self.client.get(url).status_code,403)
  self.client.logout()
  self.assertEqual(self.client.get('/admin/rollbacks/').status_code,302)
 def test_search_uses_existing_registry_and_displays_paths(self):
  response=self.client.get('/admin/modification-guide/',{'q':'invoice'})
  self.assertContains(response,'Invoice')
  self.assertContains(response,'estate_app/templates/invoices/')
  self.assertNotContains(response,'<a href="../estate_app/')
  self.assertContains(response,'instructions')
 def test_invalid_or_long_search_is_handled(self):
  self.assertEqual(self.client.get('/admin/modification-guide/',{'q':'x'*201}).status_code,200)
  response=self.client.get('/admin/modification-guide/',{'q':'<script>alert(1)</script>'})
  self.assertNotContains(response,'<script>alert(1)</script>')
 def test_catalog_exposes_only_approved_metadata_and_instructions(self):
  with TemporaryDirectory() as folder:
   root=Path(folder);snap=root/'backups/email-reminders/20260101T000000Z';snap.mkdir(parents=True)
   (snap/'manifest.json').write_text(json.dumps({'installed_commit':'a'*40,'before':'b'*40,'SECRET_KEY':'must-not-appear'}))
   (snap/'rollback-email-reminders.ps1').write_text('this must not execute')
   (snap/'OPERATIONS.md').write_text('private notes must not be served')
   (root/'.env').write_text('SECRET_KEY=must-not-appear')
   with override_settings(BASE_DIR=root):
    response=self.client.get('/admin/rollbacks/',{'path':'.env'})
    self.assertContains(response,'a'*40)
    self.assertContains(response,'rollback-email-reminders.ps1')
    self.assertNotContains(response,'must-not-appear')
    self.assertNotContains(response,'this must not execute')
    self.assertNotContains(response,'private notes must not be served')
    self.assertNotContains(response,'action="restore"')
    self.assertNotContains(response,'name="snapshot"')
 def test_catalog_handles_missing_and_invalid_metadata(self):
  with TemporaryDirectory() as folder:
   root=Path(folder)
   self.assertTrue(all(not section['snapshots'] for section in rollback_catalog(root)))
   snap=root/'backups/cursor-style/20260101';snap.mkdir(parents=True);(snap/'manifest.json').write_text('{bad json')
   result=next(section for section in rollback_catalog(root) if section['folder']=='cursor-style')
   self.assertEqual(len(result['snapshots']),1)
   self.assertEqual(result['snapshots'][0]['expected_version'],'')
 def test_symlinks_outside_backup_root_are_not_listed(self):
  with TemporaryDirectory() as folder,TemporaryDirectory() as outside:
   root=Path(folder);category=root/'backups/email-reminders';category.mkdir(parents=True)
   try:(category/'linked').symlink_to(Path(outside),target_is_directory=True)
   except OSError:self.skipTest('Creating symlinks is unavailable for this account')
   self.assertFalse(next(x for x in rollback_catalog(root) if x['folder']=='email-reminders')['snapshots'])
 def test_missing_map_reports_readable_message(self):
  with TemporaryDirectory() as folder,override_settings(BASE_DIR=Path(folder)):
   self.assertContains(self.client.get('/admin/modification-guide/'),'unavailable')
