#!/usr/bin/env python3
"""Audit and improve episode links using HN anchors, Apple IDs and RSS titles."""
import concurrent.futures as cf,datetime,html,json,re,sys,urllib.parse
from collections import Counter,defaultdict
from html.parser import HTMLParser
from pathlib import Path
from catalog_enrich import fetch,words,key,title_clean,good_title,image_url,parse_rss,itunes_feeds,merge_verified_aliases,oembed
from details import Parse
from spotify_enrich import parent as spotify_parent

class AppleMeta(HTMLParser):
 def __init__(self):super().__init__();self.meta={};self.canonical=''
 def handle_starttag(self,t,a):
  x=dict(a)
  if t=='meta':
   k=x.get('property') or x.get('name')
   if k and x.get('content'):self.meta[k]=x['content']
  if t=='link' and x.get('rel')=='canonical':self.canonical=x.get('href','')

def get_apple(job):
 (sid,eid),item=job
 try:
  raw,final=fetch(item['url'],4_000_000);p=AppleMeta();p.feed(raw.decode('utf8','replace'));u=urllib.parse.urlsplit(p.canonical or final);m=re.search(r'/id(\d+)',u.path);ep=urllib.parse.parse_qs(u.query).get('i',[''])[0]
  title=html.unescape(p.meta.get('og:title','')).strip();content=p.meta.get('apple:content_id','')
  if not m or m.group(1)!=sid or ep!=eid or content!=eid or not good_title(title):return (sid,eid),None
  return (sid,eid),{'title':title,'url':p.canonical or final,'artwork':image_url(p.meta.get('og:image',''))}
 except Exception:return (sid,eid),None

def apple_candidates(shows,raw):
 jobs={}
 for show in shows:
  sid=show['id']
  for src in show['sources']:
   cid=str(src['id']);parser=Parse();parser.feed(raw.get(cid,''))
   for link in parser.links:
    try:
     p=urllib.parse.urlsplit(html.unescape(link));m=re.search(r'/id(\d+)',p.path);eid=urllib.parse.parse_qs(p.query).get('i',[''])[0]
     if p.hostname=='podcasts.apple.com' and m and m.group(1)==sid and eid.isdigit():
      entry=jobs.setdefault((sid,eid),{'url':link,'sources':{}});entry['sources'].setdefault(cid,[]).append(link)
    except ValueError:pass
 return jobs

def main():
 shows=json.loads(Path('dist/data.json').read_text())['items'];raw=json.loads(Path('data/hn_comments.json').read_text());jobs=apple_candidates(shows,raw)
 cache_path=Path('data/apple_episode_cache.json');cache=json.loads(cache_path.read_text()) if cache_path.exists() else {};todo=[j for j in jobs.items() if '|'.join(j[0]) not in cache]
 print('Apple episode candidates:',len(jobs),'cached:',len(jobs)-len(todo),'to check:',len(todo),flush=True)
 with cf.ThreadPoolExecutor(max_workers=6) as pool:
  for index,(identity,result) in enumerate(pool.map(get_apple,todo),1):
   if result:cache['|'.join(identity)]=result
   if index%40==0:print('Checked Apple pages:',index,'/',len(todo),flush=True)
 cache_path.write_text(json.dumps(cache,ensure_ascii=False,indent=2))
 verified=sum('|'.join(k) in cache for k in jobs)
 print('Verified Apple episode pages:',verified,'/',len(jobs),flush=True)
 if len(jobs)>=20 and verified<len(jobs)*.5:raise SystemExit('Too few Apple episode pages verified; do not publish this refresh')
if __name__=='__main__':main()
