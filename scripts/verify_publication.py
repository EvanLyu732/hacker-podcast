#!/usr/bin/env python3
"""Verify that a deployed static site's JSON equals the validated local snapshot."""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def data_url(site):
    parsed = urllib.parse.urlsplit(site)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.port not in (None, 443) or parsed.path not in ('', '/')
            or parsed.query or parsed.fragment):
        raise ValueError('PUBLIC_SITE_URL must be an HTTPS site origin')
    return urllib.parse.urlunsplit(('https', parsed.netloc, '/data.json', '', ''))


def fetch_public(url):
    request = urllib.request.Request(url, headers={'Cache-Control': 'no-cache', 'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=15) as response:
        body = response.read(32 * 1024 * 1024 + 1)
        if len(body) > 32 * 1024 * 1024:
            raise ValueError('Published data.json exceeds the 32 MiB check limit')
        return json.loads(body)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def trigger_cloudflare(hook):
    parsed = urllib.parse.urlsplit(hook)
    if (parsed.scheme != 'https' or parsed.hostname != 'api.cloudflare.com'
            or parsed.username or parsed.password or parsed.port not in (None, 443)
            or not parsed.path.startswith('/client/v4/pages/webhooks/deploy_hooks/')
            or parsed.query or parsed.fragment):
        raise ValueError('CLOUDFLARE_DEPLOY_HOOK is not a valid Cloudflare Pages deploy hook')
    request = urllib.request.Request(hook, data=b'', method='POST')
    with urllib.request.build_opener(NoRedirect).open(request, timeout=15) as response:
        if response.status not in (200, 201, 202):
            raise RuntimeError('Cloudflare deploy hook was not accepted')


def verify(expected, site, hook='', attempts=16, interval=15, fetch=fetch_public,
           trigger=trigger_cloudflare, wait=time.sleep):
    url = data_url(site)
    for attempt in range(attempts):
        try:
            published = fetch(url)
            if published == expected:
                print('PUBLICATION_VERIFIED updated_at=' + expected['updated_at'], flush=True)
                return True
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        if attempt == 3 and hook:
            print('Public snapshot has not caught up; requesting a Pages deployment.', flush=True)
            trigger(hook)
        if attempt + 1 < attempts:
            wait(interval)
    print('Public data.json did not match the validated snapshot before the deadline.', file=sys.stderr)
    return False


def main():
    site = os.environ.get('PUBLIC_SITE_URL', '').strip()
    if not site:
        raise SystemExit('PUBLIC_SITE_URL is not configured; publication cannot be verified')
    expected = json.loads((ROOT / 'dist/data.json').read_text())
    try:
        ok = verify(expected, site, os.environ.get('CLOUDFLARE_DEPLOY_HOOK', '').strip())
    except (ValueError, OSError, RuntimeError) as exc:
        # Do not expose the secret deploy hook URL in workflow logs.
        raise SystemExit('Public deployment verification failed: ' + type(exc).__name__) from None
    if not ok:
        raise SystemExit('Public deployment verification failed')


if __name__ == '__main__':
    main()
