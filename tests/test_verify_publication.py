import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('verify_publication', Path(__file__).resolve().parents[1] / 'scripts/verify_publication.py')
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


class PublicVerification(unittest.TestCase):
    def test_good_origin_and_invalid_origins(self):
        self.assertEqual(check.data_url('https://example.com/'), 'https://example.com/data.json')
        for url in ('http://example.com', 'https://example.com/sub', 'https://u:p@example.com', 'https://example.com?q=x'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                check.data_url(url)

    def test_data_match_skips_hook(self):
        called = []
        expected = {'updated_at': '2026-11-05T00:00:00Z', 'items': [1]}
        self.assertTrue(check.verify(expected, 'https://example.com', hook='opaque',
                                     fetch=lambda _: expected, trigger=called.append, wait=lambda _: None))
        self.assertEqual(called, [])

    def test_stale_data_requests_hook_then_confirms(self):
        expected = {'updated_at': '2026-11-05T00:00:00Z', 'items': [1]}
        reads = iter([{}, {}, {}, {}, expected])
        called = []
        self.assertTrue(check.verify(expected, 'https://example.com', hook='opaque', attempts=5,
                                     fetch=lambda _: next(reads), trigger=called.append, wait=lambda _: None))
        self.assertEqual(called, ['opaque'])

    def test_stale_or_unavailable_data_fails(self):
        self.assertFalse(check.verify({'updated_at': 'x'}, 'https://example.com', attempts=2,
                                      fetch=lambda _: {}, wait=lambda _: None))
        def offline(_):
            raise OSError('network unavailable')
        self.assertFalse(check.verify({'updated_at': 'x'}, 'https://example.com', attempts=2,
                                      fetch=offline, wait=lambda _: None))

    def test_hook_url_is_restricted(self):
        for hook in ('http://api.cloudflare.com/client/v4/pages/webhooks/deploy_hooks/x',
                     'https://example.com/client/v4/pages/webhooks/deploy_hooks/x',
                     'https://api.cloudflare.com/other'):
            with self.subTest(hook=hook), self.assertRaises(ValueError):
                check.trigger_cloudflare(hook)


if __name__ == '__main__':
    unittest.main()
