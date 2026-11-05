import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import audit_catalog


class AuditCatalogTest(unittest.TestCase):
    def test_rss_title_for_a_different_episode_cannot_validate_association(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'dist').mkdir()
            (root / 'data').mkdir()
            trucking_url = 'https://example.com/episode/trucking'
            port_url = 'https://example.com/episode/port'
            title = 'The Trucking Episode Why the Industry Is Such a Mess'
            (root / 'dist/data.json').write_text(json.dumps({'items': [{'id': 'show', 'sources': [{'id': '1'}, {'id': '2'}]}]}))
            details = {'episodes': {'show': [
                {'title': 'Gene Seroka on the Logistical Logjam', 'url': port_url,
                 'source_ids': ['1', '2'], 'evidence': {'1': [{'method': 'rss_title', 'title': title}], '2': [{'method': 'link', 'url': port_url}]}},
                {'title': title, 'url': trucking_url, 'source_ids': ['1'],
                 'evidence': {'1': [{'method': 'rss_title', 'title': title}, {'method': 'link', 'url': trucking_url}]}},
            ]}}
            (root / 'dist/details.json').write_text(json.dumps(details))
            (root / 'data/hn_comments.json').write_text(json.dumps({'1': f'{title} <a href="{trucking_url}">episode</a>', '2': f'<a href="{port_url}">episode</a>'}))
            old = os.getcwd()
            try:
                os.chdir(root)
                with contextlib.redirect_stdout(io.StringIO()):
                    audit_catalog.main()
            finally:
                os.chdir(old)
            result = json.loads((root / 'dist/details.json').read_text())['episodes']['show']
            self.assertEqual(result[0]['source_ids'], ['2'])
            self.assertEqual(result[1]['source_ids'], ['1'])
            self.assertEqual(set(result[0]['evidence']), {'2'})


if __name__ == '__main__':
    unittest.main()
