#!/usr/bin/env python3
"""Verify that each episode/comment association has a source link or exact title evidence."""
import html,json,re,sys
from collections import defaultdict
from pathlib import Path
from details import Parse
from catalog_enrich import key,words,title_clean

def main():
 path=Path('dist/details.json');d=json.loads(path.read_text());data=json.loads(Path('dist/data.json').read_text());raw=json.loads(Path('data/hn_comments.json').read_text());shows={s['id']:s for s in data['items']}
 legacy_path=Path('/tmp/hp-before-catalog.json');legacy=json.loads(legacy_path.read_text()) if legacy_path.exists() and '--use-legacy' in sys.argv else {'episodes':{}}
 old=defaultdict(list)
 for sid,rows in legacy.get('episodes',{}).items():
  for e in rows:
   for cid in e.get('source_ids',[e.get('source_id')]):old[(sid,str(cid),words(title_clean(e['title'])))].append(e['url'])
 cache={}
 def source(cid):
  if cid not in cache:
   markup=raw.get(cid,'');p=Parse();p.feed(markup);cache[cid]=({key(u) for u in p.links},' '+words(re.sub('<[^>]+>',' ',markup))+' ')
  return cache[cid]
 removed=total=0
 for sid,episodes in list(d['episodes'].items()):
  valid={str(s['id']) for s in shows[sid]['sources']};kept=[]
  for e in episodes:
   evidence={}
   for cid in map(str,e.get('source_ids',[e.get('source_id')])):
    if cid not in valid:removed+=1;continue
    links,text=source(cid);prior=e.get('evidence',{}).get(cid,[]);verified=[]
    for item in prior:
     if item.get('method')=='link' and key(item.get('url','')) in links:verified.append(item)
     if item.get('method')=='rss_title' and words(title_clean(item.get('title',''))) and words(title_clean(item['title']))==words(title_clean(e['title'])) and ' '+words(item['title'])+' ' in text:verified.append(item)
    if not verified:
     choices=[e['url']]+old.get((sid,cid,words(title_clean(e['title']))),[])
     found=next((u for u in choices if key(u) in links),None)
     if found:verified=[{'method':'link','url':found}]
     elif words(e['title']) and ' '+words(e['title'])+' ' in text:verified=[{'method':'rss_title','title':e['title']}]
    if verified:evidence[cid]=verified;total+=1
    else:removed+=1
   if evidence:e['source_ids']=sorted(evidence);e['source_id']=e['source_ids'][0];e['evidence']=evidence;kept.append(e)
  if kept:d['episodes'][sid]=kept
  else:d['episodes'].pop(sid,None)
 path.write_text(json.dumps(d,ensure_ascii=False,indent=2));print('Verified associations:',total,'unverifiable associations removed:',removed,'episodes:',sum(map(len,d['episodes'].values())))
if __name__=='__main__':main()
