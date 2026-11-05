import json,os,sys,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import catalog_enrich
from catalog_enrich import good_title,key,episode_url_key,words,guid_key,parse_rss,merge_verified_aliases,register_alias
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
 def test_link_shared_by_distinct_episode_guids_is_not_an_episode_url(self):
  rss=b'<rss><channel><link>https://example.com/show</link><item><title>The Trucking Episode Why the Industry Is Such a Mess</title><link>https://example.com/listen</link><guid>trucking-guid</guid></item><item><title>Gene Seroka on the Port of LA</title><link>https://example.com/listen</link><guid>seroka-guid</guid></item><item><title>Another Distinct Podcast Episode</title><link>https://example.com/episode/three</link><guid>third-guid</guid></item></channel></rss>'
  with patch('catalog_enrich.fetch',return_value=(rss,'https://example.com/feed')):items,_=parse_rss('https://example.com/feed')
  self.assertEqual([i['url'] for i in items],['','','https://example.com/episode/three'])
  self.assertEqual([i['guid'] for i in items],['trucking-guid','seroka-guid','third-guid'])
 def test_same_guid_is_not_two_distinct_episodes(self):
  rss=b'<rss><channel><item><title>First Name For The Episode</title><link>https://example.com/ep</link><guid>one-guid</guid></item><item><title>Revised Name For The Episode</title><link>https://example.com/ep</link><guid>one-guid</guid></item></channel></rss>'
  with patch('catalog_enrich.fetch',return_value=(rss,'https://example.com/feed')):items,_=parse_rss('https://example.com/feed')
  self.assertEqual([x['url'] for x in items],['https://example.com/ep']*2)
 def test_conflicting_alias_is_never_reused(self):
  aliases={};conflicts=set();url='https://example.com/show'
  register_alias(aliases,conflicts,url,('rss','first'));register_alias(aliases,conflicts,url,('rss','second'))
  self.assertNotIn(key(url),aliases);self.assertIn(key(url),conflicts)
  register_alias(aliases,conflicts,url,('rss','first'));self.assertNotIn(key(url),aliases)
 def test_channel_artwork_is_not_episode_artwork(self):
  rss=b'<rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"><channel><itunes:image href="https://example.com/show.jpg"/><item><title>Long Episode With Default Cover</title><link>https://example.com/episode/default</link><itunes:image href="https://example.com/show.jpg"/></item><item><title>Long Episode With Its Own Cover</title><link>https://example.com/episode/unique</link><itunes:image href="https://example.com/episode.jpg"/></item></channel></rss>'
  with patch('catalog_enrich.fetch',return_value=(rss,'https://example.com/feed')):items,_=parse_rss('https://example.com/feed')
  self.assertIsNone(items[0]['artwork']);self.assertEqual(items[1]['artwork'],'https://example.com/episode.jpg')
 def test_verified_reissue_merges_comment_evidence(self):
  original={'url':'https://radiolab.org/podcast/americanish','source_id':'1','source_ids':['1'],'evidence':{'1':[{'method':'link','url':'https://radiolab.org/podcast/americanish'}]}}
  rerun={'url':'https://radiolab.org/podcast/americanish-2306','source_id':'2','source_ids':['2'],'evidence':{'2':[{'method':'link','url':'https://radiolab.org/podcast/americanish-2306'}]}}
  result=merge_verified_aliases([original,rerun]);self.assertEqual(len(result),1);self.assertEqual(set(result[0]['source_ids']),{'1','2'});self.assertEqual(set(result[0]['evidence']),{'1','2'})
 def test_distinct_query_urls_remain_distinct_in_verified_alias_merge(self):
  first={'url':'https://example.com/player?id=1','source_ids':['1']}
  second={'url':'https://example.com/player?id=2','source_ids':['2']}
  self.assertEqual(len(merge_verified_aliases([first,second])),2)
  self.assertNotEqual(episode_url_key(first['url']),episode_url_key(second['url']))
  self.assertEqual(episode_url_key('https://podcasts.apple.com/us/podcast/x/id123?i=42&l=en'),episode_url_key('https://podcasts.apple.com/us/podcast/x/id123?i=42'))
 def test_main_preserves_episodes_with_distinct_query_urls_and_guids(self):
  rss=b'<rss><channel><item><title>First Unique Episode About Apples</title><link>https://example.com/player?id=1</link><guid>first-guid</guid></item><item><title>Second Unique Episode About Bananas</title><link>https://example.com/player?id=2</link><guid>second-guid</guid></item></channel></rss>'
  show={'id':'123','title':'Example Show','feed_url':'https://example.com/feed','sources':[{'id':'1'},{'id':'2'}]}
  old={'title':'First Unique Episode About Apples','url':'https://example.com/player?id=1','source_id':'1','source_ids':['1']}
  with tempfile.TemporaryDirectory() as tmp:
   original=os.getcwd()
   try:
    os.chdir(tmp);Path('dist').mkdir();Path('data').mkdir()
    Path('dist/data.json').write_text(json.dumps({'items':[show]}))
    Path('dist/details.json').write_text(json.dumps({'episodes':{'123':[old]}}))
    Path('data/raw.json').write_text(json.dumps({'items':[]}))
    Path('data/hn_comments.json').write_text(json.dumps({'1':'First Unique Episode About Apples','2':'Second Unique Episode About Bananas'}))
    with patch('catalog_enrich.fetch',return_value=(rss,'https://example.com/feed')):
     catalog_enrich.main()
    episodes=json.loads(Path('dist/details.json').read_text())['episodes']['123']
    self.assertEqual(len(episodes),2)
    self.assertEqual({e['url']:e['source_ids'] for e in episodes},{'https://example.com/player?id=1':['1'],'https://example.com/player?id=2':['2']})
   finally:os.chdir(original)
 def test_text_normalization(self):
  self.assertEqual(words('Hello, WORLD!'),words('Hello world'))
if __name__=='__main__':unittest.main()
