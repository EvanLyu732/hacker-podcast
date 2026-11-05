import json,re,sys,unittest
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from catalog_enrich import good_title,key
from reconcile_episodes import is_show_title_only
class DataIntegrity(unittest.TestCase):
 def test_episode_identity_and_sources(self):
  data=json.loads((ROOT/'dist/data.json').read_text());details=json.loads((ROOT/'dist/details.json').read_text());shows={s['id']:s for s in data['items']}
  for sid,items in details['episodes'].items():
   self.assertIn(sid,shows);counts=Counter(key(e['url']) for e in items);self.assertTrue(all(n==1 for n in counts.values()),sid);valid={str(s['id']) for s in shows[sid]['sources']}
   for e in items:
    self.assertTrue(good_title(e['title']),e['title']);self.assertTrue(e['source_ids']);self.assertEqual(len(e['source_ids']),len(set(e['source_ids'])));self.assertTrue(set(e['source_ids'])<=valid);self.assertEqual(set(e['source_ids']),set(e.get('evidence',{})));self.assertFalse(any(is_show_title_only(p,shows[sid]['title']) for proofs in e.get('evidence',{}).values() for p in proofs))
 def test_only_exact_spotify_show_links(self):
  data=json.loads((ROOT/'dist/data.json').read_text())
  for show in data['items']:
   if show.get('spotify_url'):self.assertRegex(show['spotify_url'],r'^https://open\.spotify\.com/show/[A-Za-z0-9]+/?$')
if __name__=='__main__':unittest.main()
