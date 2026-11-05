#!/usr/bin/env python3
"""Capture source comment text and explicitly linked episodes without guessing."""
import concurrent.futures as cf, json, re, urllib.parse, urllib.request, html
from html.parser import HTMLParser
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
SHOWS={'99percentinvisible.org':'99% Invisible','lexfridman.com':'Lex Fridman Podcast','acquired.fm':'Acquired','dwarkesh.com':'The Dwarkesh Podcast','softwareengineeringdaily.com':'Software Engineering Daily','radiolab.org':'Radiolab','thisamericanlife.org':'This American Life','se-radio.net':'Software Engineering Radio','econtalk.org':'EconTalk','darknetdiaries.com':'Darknet Diaries','corecursive.com':'CoRecursive'}
def request(url):
 req=urllib.request.Request(url,headers={'User-Agent':'HackerPodcast/2.1','Accept':'application/json,text/html,*/*'})
 with urllib.request.urlopen(req,timeout=12) as r:
  data=r.read(1500001)
  if len(data)>1500000: raise ValueError('response too large')
  return data
class Parse(HTMLParser):
 def __init__(self):super().__init__();self.parts=[];self.links=[]
 def handle_starttag(self,t,a):
  if t in ('p','br'):self.parts.append('\n\n' if t=='p' else '\n')
  if t=='a':
   h=dict(a).get('href')
   if h:self.links.append(h)
 def handle_data(self,data):self.parts.append(data)
class Meta(HTMLParser):
 def __init__(self):super().__init__();self.title='';self.title_parts=[];self.in_title=False
 def handle_starttag(self,t,a):
  d=dict(a)
  if t=='meta' and (d.get('property')=='og:title' or d.get('name')=='twitter:title') and d.get('content') and not self.title:self.title=d['content']
  if t=='title':self.in_title=True
 def handle_endtag(self,t):
  if t=='title':self.in_title=False
 def handle_data(self,v):
  if self.in_title:self.title_parts.append(v)
def retrieve(cid):
 try:
  d=json.loads(request('https://hacker-news.firebaseio.com/v0/item/'+cid+'.json'))
  if not d or d.get('deleted') or d.get('dead') or not d.get('text'): return cid,None
  p=Parse();p.feed(d['text']);return cid,{'text':''.join(p.parts).strip(),'links':p.links,'full':True}
 except Exception:return cid,None
def is_episode_path(host,path):
 # This legacy Radiolab URL was verified against the show's RSS GUID and episode page.
 if host == 'radiolab.org' and path == '/story/update-crispr':return True
 if host == 'econtalk.org':
  return bool(re.fullmatch(r'/archives/\d{4}/\d{2}/[^/]+\.html',path) or re.fullmatch(r'/[a-z0-9]+(?:-[a-z0-9]+){2,}',path))
 if host == 'se-radio.net':
  return bool(re.fullmatch(r'/\d{4}/\d{2}/[^/]+',path))
 return bool(re.search(r'/(episode|episodes|podcast)/[^/]+',path,re.I))
def title_for(url):
 try:
  p=Meta();p.feed(request(url).decode('utf-8','replace'));title=html.unescape(p.title or ''.join(p.title_parts)).strip()
  title=re.sub(r'\s*[|–—]\s*(?:99% Invisible|Darknet Diaries|Acquired|Radiolab|EconTalk|Software Engineering Radio|This American Life|CoRecursive|Lex Fridman).*$', '',title,flags=re.I).strip()
  if len(title)<5 or re.search(r'^(404|access denied|just a moment|not found)',title,re.I):return None
  return title[:240]
 except Exception:return None

def main():
 data=json.loads(Path('dist/data.json').read_text());shows=data['items'];previous=json.loads(Path('dist/details.json').read_text()) if Path('dist/details.json').exists() else {'episodes':{}};known={(sid,e['url']):e for sid,rows in previous.get('episodes',{}).items() for e in rows};ids={str(s['id']) for x in shows for s in x['sources']};comments={};candidates=defaultdict(dict)
 # Use the full comments already captured by the historical scanner.
 cache_path=Path('data/hn_comments.json')
 cached=json.loads(cache_path.read_text()) if cache_path.exists() else {}
 for cid in ids:
  if cid in cached:
   parser=Parse();parser.feed(cached[cid]);comments[cid]={'text':''.join(parser.parts).strip(),'links':parser.links,'full':True}
 missing=ids-set(comments)
 if missing:
  with cf.ThreadPoolExecutor(max_workers=10) as pool:
   for cid,detail in pool.map(retrieve,missing):
    if detail:comments[cid]=detail
 print('Full HN comments:',len(comments),'/',len(ids),flush=True)
 if ids and len(comments) < len(ids)*0.8:raise SystemExit('Too many source fetches failed; existing details preserved')
 by_title={x['title'].casefold():x for x in shows}
 for show in shows:
  for source in show['sources']:
   d=comments.get(str(source['id']))
   if not d:continue
   for link in d['links']:
    try:
     u=urllib.parse.urlsplit(html.unescape(link));host=(u.hostname or '').lower().removeprefix('www.');path=u.path.rstrip('/')
     if u.scheme not in ('https','http'):continue
     if host=='podcasts.apple.com':
      m=re.search(r'/id(\d+)',path);episode=urllib.parse.parse_qs(u.query).get('i',[])
      if not m or m.group(1)!=show['id'] or not episode or not episode[0].isdigit():continue
      key=f'apple:{episode[0]}'
      entry=candidates[show['id']].setdefault(key,{'url':'https://podcasts.apple.com'+path+'?i='+episode[0],'source_id':str(source['id']),'source_ids':[],'apple_episode_id':episode[0]})
      if str(source['id']) not in entry['source_ids']:entry['source_ids'].append(str(source['id']))
     elif host in SHOWS and SHOWS[host].casefold()==show['title'].casefold() and is_episode_path(host,path) and not path.endswith('/transcript'):
      # Only exact, preapproved show hosts; use HTTPS and drop tracking parameters.
      url='https://'+('www.econtalk.org' if host=='econtalk.org' else host)+path
      entry=candidates[show['id']].setdefault(url,{'url':url,'source_id':str(source['id']),'source_ids':[]})
      if str(source['id']) not in entry['source_ids']:entry['source_ids'].append(str(source['id']))
    except ValueError:continue
 jobs=[]
 with cf.ThreadPoolExecutor(max_workers=8) as pool:
  for sid,entries in candidates.items():
   for item in entries.values():
    if (sid,item['url']) in known:
     future=cf.Future();future.set_result(known[(sid,item['url'])]['title'])
    elif 'apple_episode_id' in item:
     def apple_title(episode_id):
      try:
       d=json.loads(request('https://itunes.apple.com/lookup?id='+episode_id+'&entity=podcastEpisode'))
       x=next((x for x in d.get('results',[]) if str(x.get('trackId'))==episode_id and x.get('kind') in ('podcast-episode','podcastEpisode')),None)
       return x.get('trackName') if x else None
      except Exception:return None
     future=pool.submit(apple_title,item['apple_episode_id'])
    else:future=pool.submit(title_for,item['url'])
    jobs.append((sid,item,future))
  episodes=defaultdict(list)
  for sid,item,f in jobs:
   title=f.result()
   if title:
    entry={'title':title,'url':item['url'],'source_id':item['source_id'],'source_ids':item['source_ids']}
    old=known.get((sid,item['url']),{})
    for field in ('artwork','artwork_source'):
     if old.get(field):entry[field]=old[field]
    episodes[sid].append(entry)
 result={'generated_at':datetime.now(timezone.utc).isoformat(),'comments':comments,'episodes':dict(episodes)}
 # Keep raw anchor targets out of the public artifact; only validated episode links are needed.
 for c in result['comments'].values():c.pop('links',None)
 Path('dist/details.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
 print('Verified episode links:',sum(len(v) for v in episodes.values()),'shows:',len(episodes),flush=True)
if __name__=='__main__':main()
