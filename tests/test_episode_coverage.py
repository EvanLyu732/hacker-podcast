import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from episode_coverage import apple_candidates,get_apple
from rss_coverage import title_match
from reconcile_episodes import identity_apple,is_show_title_only,confirmed_existing_rss_alias
from details import is_episode_path

class EpisodeCoverage(unittest.TestCase):
 def test_only_verified_legacy_radiolab_story_path_is_accepted(self):
  self.assertTrue(is_episode_path('radiolab.org','/story/update-crispr'))
  self.assertFalse(is_episode_path('radiolab.org','/story/unverified-story'))
  self.assertFalse(is_episode_path('example.org','/story/update-crispr'))
 def test_short_rss_title_requires_same_episode_link_for_every_comment(self):
  url='https://example.com/episode/mcmansion-hell';entry={'title':'McMansion Hell: The Devil is in the Details','url':url,'source_ids':['1','2']};raw={'1':f'<a href="{url}">listen</a>','2':f'<a href="{url}">listen</a>'}
  self.assertTrue(confirmed_existing_rss_alias('McMansion Hell',['1','2'],[entry],raw))
  self.assertFalse(confirmed_existing_rss_alias('McMansion Hell',['1','2'],[entry],{'1':raw['1'],'2':'no link'}))
  self.assertFalse(confirmed_existing_rss_alias('McMansion Hell',['1'],[{**entry,'title':'McMansion Hell Redux'}],raw))
  self.assertTrue(confirmed_existing_rss_alias('Mini-Stories: Volume 8',['1'],[{**entry,'title':'Mini-Stories: Volume 8 - Page 2 of 4'}],raw))
  self.assertFalse(confirmed_existing_rss_alias('Mini-Stories: Volume 1',['1'],[{**entry,'title':'Mini-Stories: Volume 17'}],raw))
 def test_direct_apple_id_requires_correct_show(self):
  shows=[{'id':'123','sources':[{'id':'1'}]},{'id':'999','sources':[{'id':'1'}]}]
  raw={'1':'<a href="https://podcasts.apple.com/us/podcast/name/id123?i=456">episode</a>'}
  found=apple_candidates(shows,raw);self.assertEqual(set(found),{('123','456')})
 def test_apple_page_requires_episode_and_show_ids(self):
  page=b'<link rel="canonical" href="https://podcasts.apple.com/us/podcast/test/id123?i=456"><meta name="apple:content_id" content="456"><meta property="og:title" content="A Real Episode Title">'
  job=(('123','456'),{'url':'https://podcasts.apple.com/us/podcast/test/id123?i=456','sources':{}})
  with patch('episode_coverage.fetch',return_value=(page,job[1]['url'])):self.assertEqual(get_apple(job)[1]['title'],'A Real Episode Title')
  with patch('episode_coverage.fetch',return_value=(page.replace(b'content="456"',b'content="123"'),job[1]['url'])):self.assertIsNone(get_apple(job)[1])
 def test_rss_short_title_needs_episode_context(self):
  self.assertEqual(title_match('The Wubi Effect','A podcast episode called The Wubi Effect is excellent.'),'context_title')
  self.assertIsNone(title_match('The Wubi Effect','The Wubi Effect is interesting.'))
  self.assertIsNone(title_match('The Story','This podcast episode The Story is good.'))
 def test_show_name_is_not_evidence_of_specific_episode(self):
  self.assertTrue(is_show_title_only({'method':'rss_title','title':"Let's Talk About CBT"},"Let's Talk About CBT"))
  self.assertFalse(is_show_title_only({'method':'link','url':'https://example.com'},"Let's Talk About CBT"))
  self.assertFalse(is_show_title_only({'method':'rss_title','title':'CBT for Depression'},"Let's Talk About CBT"))
 def test_apple_identity_ignores_slug_but_not_episode_id(self):
  self.assertEqual(identity_apple('https://podcasts.apple.com/us/podcast/name/id123?i=456'),identity_apple('https://podcasts.apple.com/gb/podcast/other/id123?i=456'))
  self.assertNotEqual(identity_apple('https://podcasts.apple.com/us/podcast/name/id123?i=456'),identity_apple('https://podcasts.apple.com/us/podcast/name/id123?i=457'))
if __name__=='__main__':unittest.main()
