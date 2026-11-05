import copy
import datetime as dt
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('refresh_pipeline', Path(__file__).resolve().parents[1] / 'scripts/refresh_pipeline.py')
refresh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(refresh)


class RefreshGateTest(unittest.TestCase):
    def setUp(self):
        self.started = dt.datetime(2026, 11, 5, 7, 0, tzinfo=dt.timezone.utc)
        self.finished = self.started + dt.timedelta(minutes=1)
        self.old = {'updated_at': '2026-11-04T07:00:00Z', 'source_cutoff_id': 10,
                    'items': [{'id': 'show', 'spotify_url': 'https://open.spotify.com/show/1', 'sources': [{'id': 'comment'}]}]}
        self.new = copy.deepcopy(self.old)
        self.new.update(updated_at='2026-11-05T07:00:30Z', source_cutoff_id=11)
        self.details = {'episodes': {'show': [{'source_ids': ['comment']}]}}
        self.audit = {'data_snapshot': self.new['updated_at']}

    def check(self, new=None, details=None, audit=None):
        return refresh.validate(self.old, new or self.new, self.details, details or self.details,
                                audit or self.audit, self.started, self.finished)

    def test_valid_refresh(self):
        self.assertEqual(self.check()['unique_comments'], 1)

    def test_stale_or_forged_timestamp_rejected(self):
        for timestamp in [self.old['updated_at'], '2026-11-05T07:05:00Z']:
            with self.subTest(timestamp=timestamp), self.assertRaises(ValueError):
                self.check(new={**self.new, 'updated_at': timestamp})

    def test_lost_data_and_duplicate_show_rejected(self):
        for items in [[], self.new['items'] * 2,
                      [{**self.new['items'][0], 'sources': []}],
                      [{**self.new['items'][0], 'spotify_url': ''}]]:
            with self.subTest(items=items), self.assertRaises(ValueError):
                self.check(new={**self.new, 'items': items})

    def test_restore_previous_verified_artwork_only_for_same_episode(self):
        old = {'episodes': {'show': [
            {'url': 'https://www.example.com/episode/one/', 'artwork': 'https://example.com/one.jpg', 'artwork_source': 'episode_page'},
            {'url': 'https://example.com/episode/two', 'artwork': 'https://example.com/two.jpg'},
            {'url': 'https://podcasts.apple.com/us/podcast/id123?i=10', 'artwork': 'https://example.com/ten.jpg'},
        ]}}
        new = {'episodes': {'show': [
            {'url': 'https://example.com/episode/one'},
            {'url': 'https://example.com/episode/two', 'artwork': 'https://example.com/new.jpg'},
            {'url': 'https://podcasts.apple.com/us/podcast/id123?i=11'},
        ]}}
        self.assertEqual(refresh.preserve_episode_artwork(old, new), 1)
        self.assertEqual(new['episodes']['show'][0]['artwork'], 'https://example.com/one.jpg')
        self.assertEqual(new['episodes']['show'][0]['artwork_source'], 'episode_page')
        self.assertEqual(new['episodes']['show'][1]['artwork'], 'https://example.com/new.jpg')
        self.assertNotIn('artwork', new['episodes']['show'][2])

    def test_episode_association_and_mismatched_audit_rejected(self):
        with self.assertRaises(ValueError):
            self.check(details={'episodes': {}})
        with self.assertRaises(ValueError):
            self.check(audit={'data_snapshot': 'different'})


if __name__ == '__main__':
    unittest.main()
