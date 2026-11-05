#!/usr/bin/env python3
"""Match Apple and Spotify show IDs through Wikidata, verifying the Spotify page title."""
import json,sys,urllib.parse,urllib.request,concurrent.futures as cf,collections,time
from pathlib import Path
sys.path.insert(0,'scripts');from catalog_enrich import oembed,words
p=Path('dist/data.json');d=json.loads(p.read_text());ids=[x['id'] for x in d['items'] if str(x['id']).isdigit()];pairs=[]
for n in range(0,len(ids),50):
 vals=' '.join('"'+v+'"' for v in ids[n:n+50]);q='SELECT ?item ?a ?s WHERE { VALUES ?a { '+vals+' } ?item wdt:P5842 ?a; wdt:P5916 ?s. }'
 u='https://query.wikidata.org/sparql?'+urllib.parse.urlencode({'query':q,'format':'json'});req=urllib.request.Request(u,headers={'User-Agent':'HackerPodcast/2.3 (podcast catalog)'})
 for attempt in range(3):
  try:
   with urllib.request.urlopen(req,timeout=30) as r:arr=json.load(r)['results']['bindings']
   pairs.extend((x['a']['value'],x['s']['value']) for x in arr);break
  except Exception as e:
   if attempt==2:raise SystemExit('Wikidata unavailable; do not publish this refresh') from e
   time.sleep(2**attempt)
print('Wikidata candidate associations',len(pairs),flush=True)
byid={s['id']:s for s in d['items']};candidates={(sid,'https://open.spotify.com/show/'+sp) for sid,sp in pairs if sid in byid and sp.isalnum() and len(sp)==22}
with cf.ThreadPoolExecutor(max_workers=8) as pool:
 results=list(pool.map(lambda x:(x[0],oembed(x[1])),candidates))
if results and sum(bool(title) for _,(_,title) in results)<max(1,int(len(results)*.5)):
 raise SystemExit('Spotify verification unavailable; do not publish this refresh')
verified=collections.defaultdict(set)
for sid,(link,title) in results:
 if title and words(title)==words(byid[sid]['title']):verified[sid].add(link)
added=0;conflicts=[]
for sid,links in verified.items():
 current=byid[sid].get('spotify_url')
 if current:links.add(current.rstrip('/'))
 if len(links)==1 and not current:byid[sid]['spotify_url']=next(iter(links));added+=1
 elif len(links)>1:conflicts.append((byid[sid]['title'],len(links)))
p.write_text(json.dumps(d,ensure_ascii=False,indent=2));stamp=d['updated_at'][:10];Path('snapshots',stamp+'.json').write_text(json.dumps(d,ensure_ascii=False));Path('snapshots',stamp+'-details.json').write_text(Path('dist/details.json').read_text());print('Added exact title verified',added,'conflicts preserved existing',len(conflicts),'total',sum(bool(x.get('spotify_url')) for x in d['items']))
