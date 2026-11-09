import json
from pathlib import Path
import tempfile
import unittest
from build_component_map import load_registry, render_markdown, render_html, generate

class ComponentMapTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name);(self.root/'docs').mkdir();(self.root/'src').mkdir()
  (self.root/'src/screen.jsx').write_text('export function Screen() { return null; }')
  self.registry={'title':'Test map','intro':'Edit safely.','inventory_roots':['src'],'components':[{'id':'app','title':'Application','purpose':'App <shell>','parent':None,'files':[{'path':'src/screen.jsx','role':'Screen','symbols':['Screen']}],'tests':[],'settings':'None','caution':'Keep behavior.'}],'recipes':[{'title':'Change screen','components':['app'],'steps':['Edit Screen.']}]}
  self.path=self.root/'docs/component-map.json';self.save()
 def save(self):self.path.write_text(json.dumps(self.registry))
 def test_generate_links_escaped_html_and_detect_stale_outputs(self):
  data=load_registry(self.root,self.path)
  self.assertIn('../src/screen.jsx',render_markdown(data))
  html=render_html(data);self.assertIn('App &lt;shell&gt;',html);self.assertIn('type="search"',html);self.assertIn('<details',html)
  self.assertTrue(generate(self.root,self.path,check=False))
  self.assertTrue(generate(self.root,self.path,check=True))
  (self.root/'docs/COMPONENT-MAP.md').write_text('outdated')
  self.assertFalse(generate(self.root,self.path,check=True))
 def test_missing_files_symbols_cycles_and_unmapped_code_are_rejected(self):
  original=json.loads(json.dumps(self.registry))
  changes=[lambda d:d['components'][0]['files'][0].update(path='missing.py'),lambda d:d['components'][0]['files'][0].update(symbols=['MissingSymbol']),lambda d:d['components'][0].update(parent='app'),lambda d:d['recipes'][0].update(components=['missing'])]
  for change in changes:
   self.registry=json.loads(json.dumps(original));change(self.registry);self.save()
   with self.subTest(change=change),self.assertRaises(ValueError):load_registry(self.root,self.path)
  self.registry=original;self.save();(self.root/'src/new.py').write_text('pass')
  with self.assertRaisesRegex(ValueError,'Unmapped'):load_registry(self.root,self.path)
 def test_external_or_private_paths_are_rejected(self):
  for path in ['../private.txt','.env','outputs/example.py',str(self.root/'src/screen.jsx')]:
   self.registry['components'][0]['files'][0]['path']=path;self.save()
   with self.subTest(path=path),self.assertRaises(ValueError):load_registry(self.root,self.path)
