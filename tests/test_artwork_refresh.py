import importlib.util
import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
spec = importlib.util.spec_from_file_location('episode_artwork', Path(__file__).resolve().parents[1] / 'scripts/episode_artwork.py')
artwork = importlib.util.module_from_spec(spec)
spec.loader.exec_module(artwork)


class ArtworkRefreshTest(unittest.TestCase):
    def test_empty_episode_image_is_not_the_feed_url(self):
        self.assertIsNone(artwork.image_url(None, 'https://example.com/feed.xml'))
        self.assertIsNone(artwork.image_url('', 'https://example.com/feed.xml'))
        self.assertIsNone(artwork.image_url('  ', 'https://example.com/feed.xml'))
        self.assertEqual(artwork.image_url('/cover.jpg', 'https://example.com/feed.xml'), 'https://example.com/cover.jpg')

    def test_rss_does_not_treat_missing_or_show_art_as_episode_art(self):
        rss = b'''<rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"><channel>
          <itunes:image href="https://example.com/show.jpg"/>
          <item><title>No image</title></item>
          <item><title>Show image</title><itunes:image href="https://example.com/show.jpg"/></item>
          <item><title>Episode image</title><itunes:image href="https://example.com/episode.jpg"/></item>
          <item><title>Nested episode image</title><image><url>https://example.com/nested.jpg</url></image></item>
        </channel></rss>'''
        with mock.patch.object(artwork, 'fetch', return_value=(rss, 'https://example.com/feed.xml')):
            items = artwork.rss_images('https://example.com/feed.xml')
        self.assertEqual([item['artwork'] for item in items], [None, None, 'https://example.com/episode.jpg', 'https://example.com/nested.jpg'])

    def test_episode_url_matching_preserves_episode_query(self):
        a = 'https://podcasts.apple.com/us/podcast/example/id123?i=1'
        b = 'https://podcasts.apple.com/us/podcast/example/id123?i=2'
        self.assertNotEqual(artwork.norm_url(a), artwork.norm_url(b))

    def test_episode_page_image_requires_matching_title_and_show_host(self):
        page = b'<meta property="og:title" content="A Distinct Episode Title - This American Life"><meta property="og:image" content="https://example.com/episode.jpg">'
        url = 'https://thisamericanlife.org/123/example'
        with mock.patch.object(artwork, 'fetch', return_value=(page, url)):
            self.assertEqual(artwork.page_image(url, 'A Distinct Episode Title - This American Life'), 'https://example.com/episode.jpg')
            self.assertIsNone(artwork.page_image(url, 'A Different Episode Title'))
        with mock.patch.object(artwork, 'fetch', return_value=(page, 'https://unrelated.example/123/example')):
            self.assertIsNone(artwork.page_image(url, 'A Distinct Episode Title'))

    def test_rss_matches_only_unique_titles_and_preserves_existing_art(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'dist').mkdir()
            (root / 'dist/data.json').write_text(json.dumps({'items': [{'id': 'show', 'feed_url': 'https://example.com/feed', 'artwork': 'https://example.com/show.jpg'}]}))
            episodes = [
                {'title': 'A Unique Episode Title', 'url': 'https://example.com/unique'},
                {'title': 'A Repeated Episode Title', 'url': 'https://example.com/repeated-one'},
                {'title': 'A Repeated Episode Title', 'url': 'https://example.com/repeated-two'},
                {'title': 'Existing Good Episode Image', 'url': 'https://example.com/existing', 'artwork': 'https://example.com/old.jpg', 'artwork_source': 'episode_page'},
            ]
            (root / 'dist/details.json').write_text(json.dumps({'episodes': {'show': episodes}}))
            items = [
                {'title': artwork.norm_title('A Unique Episode Title'), 'url': artwork.norm_url(''), 'guid': artwork.norm_url(''), 'artwork': 'https://example.com/new.jpg'},
                {'title': artwork.norm_title('A Repeated Episode Title'), 'url': artwork.norm_url(''), 'guid': artwork.norm_url(''), 'artwork': 'https://example.com/ambiguous.jpg'},
                {'title': artwork.norm_title('Existing Good Episode Image'), 'url': artwork.norm_url(''), 'guid': artwork.norm_url(''), 'artwork': 'https://example.com/replacement.jpg'},
            ]
            old_cwd = os.getcwd()
            try:
                os.chdir(root)
                with mock.patch.object(artwork, 'rss_images', return_value=items), mock.patch.object(artwork, 'page_image', return_value=None):
                    artwork.main()
            finally:
                os.chdir(old_cwd)
            result = json.loads((root / 'dist/details.json').read_text())['episodes']['show']
            self.assertEqual(result[0]['artwork'], 'https://example.com/new.jpg')
            self.assertNotIn('artwork', result[1])
            self.assertNotIn('artwork', result[2])
            self.assertEqual(result[3]['artwork'], 'https://example.com/old.jpg')

    def test_existing_episode_art_survives_unavailable_sources(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'dist').mkdir()
            (root / 'dist/data.json').write_text(json.dumps({'items': [{'id': 'show', 'feed_url': 'https://example.com/feed'}]}))
            (root / 'dist/details.json').write_text(json.dumps({'episodes': {'show': [{'title': 'An episode',
                'url': 'https://example.com/episode/1', 'artwork': 'https://example.com/episode.jpg', 'artwork_source': 'rss'}]}}))
            old_cwd = os.getcwd()
            try:
                os.chdir(root)
                with mock.patch.object(artwork, 'rss_images', return_value=[]), \
                     mock.patch.object(artwork, 'page_image', return_value=None):
                    artwork.main()
            finally:
                os.chdir(old_cwd)
            episode = json.loads((root / 'dist/details.json').read_text())['episodes']['show'][0]
            self.assertEqual(episode['artwork'], 'https://example.com/episode.jpg')
            self.assertEqual(episode['artwork_source'], 'rss')


if __name__ == '__main__':
    unittest.main()
