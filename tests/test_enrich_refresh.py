import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location('enrich', Path(__file__).resolve().parents[1] / 'scripts/enrich.py')
enrich = importlib.util.module_from_spec(spec)
spec.loader.exec_module(enrich)


class EnrichmentRefreshTest(unittest.TestCase):
    def test_preserves_verified_spotify_and_prior_rss_when_feed_unavailable(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'snapshots').mkdir()
            raw = root / 'raw.json'
            out = root / 'data.json'
            raw.write_text(json.dumps({'items': [{'url': 'https://podcasts.apple.com/us/podcast/id123',
                                                  'sources': [{'id': '1', 'date': '2026-01-01'}]}],
                                       'queries': [], 'pages_per_query': 1, 'scanned_unique_comments': 1}))
            out.write_text(json.dumps({'items': [{'id': '123', 'spotify_url': 'https://open.spotify.com/show/verified',
                                                   'feed_url': 'https://example.com/rss', 'description': 'previous',
                                                   'latest_episode': {'title': 'previous episode'}}]}))
            metadata = {'results': [{'kind': 'podcast', 'collectionId': 123, 'collectionName': 'Show',
                                     'collectionViewUrl': 'https://podcasts.apple.com/id123',
                                     'feedUrl': 'https://example.com/rss'}]}
            with mock.patch.object(enrich, 'RAW', raw), mock.patch.object(enrich, 'OUT', out), \
                 mock.patch.object(enrich, 'get_json', return_value=metadata), \
                 mock.patch.object(enrich, 'rss', return_value=None), \
                 mock.patch.object(enrich.time, 'sleep'):
                # snapshots is relative to the working directory in the production script.
                import os
                old_cwd = os.getcwd()
                try:
                    os.chdir(root)
                    enrich.main()
                finally:
                    os.chdir(old_cwd)
            show = json.loads(out.read_text())['items'][0]
            self.assertEqual(show['spotify_url'], 'https://open.spotify.com/show/verified')
            self.assertEqual(show['feed_url'], 'https://example.com/rss')
            self.assertEqual(show['latest_episode']['title'], 'previous episode')
            self.assertEqual(show['description'], 'previous')


if __name__ == '__main__':
    unittest.main()
