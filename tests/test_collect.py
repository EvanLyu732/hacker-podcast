import contextlib, importlib.util, io, json, os, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('collector',ROOT/'scripts/collect.py');c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)

class CollectionTest(unittest.TestCase):
 def run_scan(self,mismatch=False):
  def query(sql):
   if 'max(id)' in sql:return [{'max_id':3,'latest_time':'2026-01-01 00:00:00'}]
   if 'GROUP BY p' in sql:return [{'p':0,'total':3,'candidates':2 if mismatch else 1}]
   return [{'id':1,'by':'person','time':'2025-01-01 00:00:00','text':'I recommend this podcast <a href="https://podcasts.apple.com/us/podcast/example/id123">Example</a>'}]
  with patch.object(c,'query',side_effect=query),contextlib.redirect_stdout(io.StringIO()):c.main()
 def test_full_partition_and_source_cache(self):
  old=os.getcwd()
  with tempfile.TemporaryDirectory() as tmp:
   try:
    os.chdir(tmp);self.run_scan();raw=json.loads(Path('data/raw.json').read_text());cache=json.loads(Path('data/hn_comments.json').read_text());self.assertEqual(raw['scanned_unique_comments'],3);self.assertEqual(raw['matched_comments'],1);self.assertEqual(raw['source_cutoff_id'],3);self.assertEqual(raw['items'][0]['sources'][0]['id'],'1');self.assertIn('podcast',cache['1'])
   finally:os.chdir(old)
 def test_partition_mismatch_does_not_overwrite(self):
  old=os.getcwd()
  with tempfile.TemporaryDirectory() as tmp:
   try:
    os.chdir(tmp);Path('data').mkdir();Path('data/raw.json').write_text('previous');
    with self.assertRaises(RuntimeError):self.run_scan(mismatch=True)
    self.assertEqual(Path('data/raw.json').read_text(),'previous')
   finally:os.chdir(old)
if __name__=='__main__':unittest.main()
