import sys,unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from catalog_enrich import good_title,key,words,guid_key,parse_rss,merge_verified_aliases
class CatalogTest(unittest.TestCase):
 def test_noise_rejected(self):
  for title in ('dawgyg','Podcast Episode','Podcast Episode - 99% Invisible','Podcast Episode 123','404 Not Found'):
   self.assertFalse(good_title(title),title)
  self.assertTrue(good_title('The Wubi Effect'))
 def test_url_id_and_tracking(self):
  self.assertEqual(key('http://www.example.com/episode/hello/?utm_source=x'),key('https://example.com/episode/hello'))
  self.assertNotEqual(key('https://podcasts.apple.com/us/podcast/name/id123?i=11'),key('https://podcasts.apple.com/us/podcast/name/id123?i=12'))
 def test_guid_query_preserved(self):
  self.assertNotEqual(guid_key('https://example.com/?p=1'),guid_key('https://example.com/?p=2'))
 def test_generic_feed_link_is_not_an_episode(self):
  rss=b'<rss><channel><item><title>A Distinct Episode Title</title><link>https://example.com/</link><guid>https://example.com/?p=42</guid></item></channel></rss>'
  with patch('catalog_enrich.fetch',return_value=(rss,'https://example.com/feed')):
   items,_=parse_rss('https://example.com/feed')
  self.assertEqual(items[0]['url'],'');self.assertNotEqual(guid_key(items[0]['guid']),guid_key('https://example.com/?p=43'))
 def test_channel_artwork_is_not_episode_artwork(self):
  rss=b'<rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"><channel><itunes:image href="https://example.com/show.jpg"/><item><title>Long Episode With Default Cover</title><link>https://example.com/episode/default</link><itunes:image href="https://example.com/show.jpg"/></item><item><title>Long Episode With Its Own Cover</title><link>https://example.com/episode/unique</link><itunes:image href="https://example.com/episode.jpg"/></item></channel></rss>'
  with patch('catalog_enrich.fetch',return_value=(rss,'https://example.com/feed')):items,_=parse_rss('https://example.com/feed')
  self.assertIsNone(items[0]['artwork']);self.assertEqual(items[1]['artwork'],'https://example.com/episode.jpg')
 def test_verified_reissue_merges_comment_evidence(self):
  original={'url':'https://radiolab.org/podcast/americanish','source_id':'1','source_ids':['1'],'evidence':{'1':[{'method':'link','url':'https://radiolab.org/podcast/americanish'}]}}
  rerun={'url':'https://radiolab.org/podcast/americanish-2306','source_id':'2','source_ids':['2'],'evidence':{'2':[{'method':'link','url':'https://radiolab.org/podcast/americanish-2306'}]}}
  result=merge_verified_aliases([original,rerun]);self.assertEqual(len(result),1);self.assertEqual(set(result[0]['source_ids']),{'1','2'});self.assertEqual(set(result[0]['evidence']),{'1','2'})
 def test_text_normalization(self):
  self.assertEqual(words('Hello, WORLD!'),words('Hello world'))
if __name__=='__main__':unittest.main()
