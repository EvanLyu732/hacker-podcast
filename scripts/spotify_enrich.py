#!/usr/bin/env python3
"""Map Spotify episode links to their parent show and verify show names on the Spotify show page."""
import concurrent.futures as cf,json,re,sys
from collections import defaultdict
from pathlib import Path
from catalog_enrich import fetch,oembed,words

# Public episode URLs used only as candidates; every resulting show is verified by show page metadata.
SEEDS=['https://open.spotify.com/episode/77Kl3BsiEQLpli2Q2ozZuf','https://open.spotify.com/episode/043y0OMtTiIyZwMI0WVGlJ','https://open.spotify.com/episode/0KJb56cqwhmmb3b2PJqqVS','https://open.spotify.com/episode/4K53Plnt9OUCcpBv7ihAfz','https://open.spotify.com/episode/3b8Kuz0KuGt74FUvR7B80J']
SEED_SHOWS=['https://open.spotify.com/show/6UCtBYL29hwhw4YbTdX83N','https://open.spotify.com/show/6E709HRH7XaiZrMfgtNCun']
def parent(url):
 try:
  body,_=fetch(url,3_000_000);text=body.decode('utf8','replace');match=re.search(r'</h1>\s*<a[^>]*href="/show/([A-Za-z0-9]+)"',text)
  return 'https://open.spotify.com/show/'+match.group(1) if match else None
 except Exception:return None
def main():
 data=Path('dist/data.json');raw=json.loads(Path('data/raw.json').read_text());shows=json.loads(data.read_text());urls={r['url'] for r in raw['items'] if re.fullmatch(r'https?://open\.spotify\.com/episode/[A-Za-z0-9]+/?',r['url'])};urls.update(SEEDS)
 if '--use-gathered' in sys.argv:
  candidates=set(SEED_SHOWS)|{row[0] for row in json.loads(Path('/tmp/hp-spotify-verified.json').read_text())};candidates.update(r['url'].rstrip('/') for r in raw['items'] if re.fullmatch(r'https?://open\.spotify\.com/show/[A-Za-z0-9]+/?',r['url']));
  with cf.ThreadPoolExecutor(max_workers=8) as pool:verified=list(pool.map(oembed,candidates))
 else:
  with cf.ThreadPoolExecutor(max_workers=8) as pool:parents={p for p in pool.map(parent,urls) if p}
  parents.update(SEED_SHOWS)
  print('Resolved parent show candidates:',len(parents),flush=True)
  with cf.ThreadPoolExecutor(max_workers=8) as pool:verified=list(pool.map(oembed,parents))
 if not verified or sum(bool(title) for _,title in verified)<max(1,int(len(verified)*.25)):
  raise SystemExit('Spotify verification unavailable; do not publish this refresh')
 if '--gather-only' in sys.argv:
  Path('/tmp/hp-spotify-verified.json').write_text(json.dumps(verified,ensure_ascii=False));print('Verified candidates:',len(verified),flush=True);return
 names=defaultdict(list)
 for s in shows['items']:names[words(s['title'])].append(s)
 matching=defaultdict(set)
 for link,title in verified:
  n=words(title)
  if n and len(names[n])==1:matching[names[n][0]['id']].add(link)
 for s in shows['items']:
  prior=s.get('spotify_url')
  if prior:matching[s['id']].add(prior.rstrip('/'))
  if len(matching[s['id']])==1:s['spotify_url']=next(iter(matching[s['id']]))
  else:s.pop('spotify_url',None)
 data.write_text(json.dumps(shows,ensure_ascii=False,indent=2))
 archive=Path('snapshots');archive.mkdir(exist_ok=True);stamp=shows['updated_at'][:10]
 (archive/(stamp+'.json')).write_text(json.dumps(shows,ensure_ascii=False))
 (archive/(stamp+'-details.json')).write_text(Path('dist/details.json').read_text())
 print('Verified Spotify shows:',sum(bool(x.get('spotify_url')) for x in shows['items']))
if __name__=='__main__':main()
