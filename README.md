# Hacker Podcast

A static collection of podcast shows linked from HN comments. UI version 3.0.6.

## Refresh

Run `python3 scripts/refresh_pipeline.py` from the repository root. It runs the
steps below in an isolated staging directory, applies completeness and
regression checks, and only copies validated results into the repository after
all steps and tests succeed. A failed refresh must not be committed or
published. For the proposed GitHub Actions and Cloudflare Pages setup, see
[MIGRATION.md](MIGRATION.md); creating the workflow alone does not configure a
hosting account or prove unattended runs have succeeded.

The pipeline runs these commands in order:

1. `python3 scripts/collect.py`
2. `python3 scripts/enrich.py`
3. `python3 scripts/details.py`
4. `python3 scripts/episode_artwork.py`
5. `python3 scripts/catalog_enrich.py`
6. `python3 scripts/episode_coverage.py` and `python3 scripts/diagnose_apple_failures.py`
7. `python3 scripts/rss_coverage.py` and `python3 scripts/rss_coverage.py --retry-unavailable`
8. `python3 scripts/spotify_episode_coverage.py`
9. `python3 scripts/reconcile_episodes.py` and `python3 scripts/audit_catalog.py`
10. `python3 scripts/spotify_enrich.py` and `python3 scripts/wikidata_spotify.py`
11. `python3 -m unittest discover -s tests -p 'test_*.py'`, `node tests/app.test.js`, `node tests/episode_views.test.js`, `node tests/daily_feature.test.js`, `node tests/share.test.js`, `node tests/search.test.js`, `node tests/artwork_referrer.test.js`, and `node tests/sorting.test.js`

After a validated refresh, commit the refreshed output and publish that exact commit using the selected hosting provider. If any required step or validation fails, do not publish. Each successful refresh archives the final data and episode details. No credentials belong in the repository. The Site is public; preserve its access settings. The public `episode-audit.md` and `episode-audit.json` list unresolved candidates and unavailable feeds; “possible” comments are not confirmed omissions. Apple episode pages are accepted only when both show and episode IDs match, Spotify episodes only after parent-show verification, and RSS titles only under conservative matching rules.

The collector screens all currently available, non-deleted and non-dead comments in the public ClickHouse `hackernews_history FINAL` mirror through a recorded maximum comment ID. It verifies candidate counts for every 500,000-ID partition and refuses to publish an incomplete or inconsistent scan. This is a rolling scan of a third-party mirror, not a transactional snapshot of Hacker News; unavailable, removed or deleted items are excluded. Filtering is heuristic: text or link must contain a podcast-related keyword or known domain, positive-language matching is imperfect, and only linked records on known domains are extracted. Show resolution is conservative, so recommendations without links, unrecognized domains, negative or ambiguous text and unresolved show IDs may be missed. `data/hn_comments.json` holds the captured public comment HTML for reproducible source attribution. The catalog pass matches unique RSS titles literally present in source comments, merges canonical episode identities, and verifies Spotify show links against Spotify show-page titles and reconciles Apple/Spotify IDs through Wikidata; unresolved Spotify links are omitted. The episode artwork collector prefers artwork from the matching RSS item, then the linked episode page; the browser falls back to the show artwork or a no-image label. The details collector retrieves full comment text and verifies explicitly linked episode titles from known show sites or Apple episode IDs and retains all comment-to-episode associations; missing text falls back to the original excerpt and unverified episodes are omitted. The enricher resolves explicit Apple podcast IDs and a small set of unambiguous show domains through the iTunes API. Other links are excluded rather than guessed. Shows merge by iTunes collection ID and deduplicate HN comment IDs. iTunes provides name, artwork, feed and genre; public HTTPS RSS feeds supply description and latest episode when available. Failed RSS requests degrade gracefully. Plain HTTP feed URLs are tried over HTTPS only. Redirects and feeds resolving to private addresses are rejected. No frontend fan-out to external APIs occurs. Classification is intentionally absent until reliable coverage is available.

Automated DOM simulation: `node tests/app.test.js`. This is not a browser test.
