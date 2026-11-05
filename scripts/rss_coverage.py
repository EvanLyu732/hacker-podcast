#!/usr/bin/env python3
"""Check every show against its RSS episode titles and retain conservative matches."""
import concurrent.futures as cf,json,re,sys
from collections import Counter
from pathlib import Path
from catalog_enrich import itunes_feeds,parse_rss,words,good_title

def title_match(title,text,normalized=False):
 name=words(title);parts=name.split()
 if len(name)<12 or len(parts)<2:return None
 if name in {'the interview','the story','the podcast','the episode','the show','the future','the beginning','the end'}:return None
 content=text if normalized else ' '+words(re.sub('<[^>]*>',' ',text or ''))+' ';needle=' '+name+' ';pos=content.find(needle)
 if pos<0:return None
 if len(name)>=20 and len(parts)>=4 and len(set(parts))>=3:return 'exact_title'
 nearby=content[max(0,pos-70):min(len(content),pos+len(needle)+70)]
 if re.search(r'\b(?:episode|episodes|podcast|interview|listen|listened|listening|ep)\b',nearby):return 'context_title'
 return None

def main():
 data=json.loads(Path('dist/data.json').read_text());comments=json.loads(Path('data/hn_comments.json').read_text());shows=data['items'];cache=Path('data/rss_match_candidates.json');previous=json.loads(cache.read_text()) if '--retry-unavailable' in sys.argv and cache.exists() else None;targets=[s for s in shows if not previous or previous['shows'].get(s['id'],{}).get('feed_status')!='available'];fallback=itunes_feeds(targets)
 jobs={};results={}
 with cf.ThreadPoolExecutor(max_workers=3) as pool:
  for show in targets:
   feed=show.get('feed_url') or fallback.get(show['id'])
   if feed:jobs[show['id']]=pool.submit(parse_rss,feed)
  for idx,(sid,f) in enumerate(jobs.items(),1):
   rows,_=f.result();results[sid]=rows
   if idx%50==0:print('Checked RSS feeds',idx,'/',len(jobs),flush=True)
 out=dict(previous['shows']) if previous else {};total=0;without_link=0;collisions=0
 for show in targets:
  sid=show['id'];rows=results.get(sid,[]);counts=Counter(words(r['title']) for r in rows);sources=[(str(s['id']),' '+words(re.sub('<[^>]*>',' ',comments.get(str(s['id']),s.get('text',''))))+' ') for s in show['sources']];matches=[]
  for item in rows:
   name=words(item['title'])
   if counts[name]!=1:collisions+=1;continue
   hits=[{'id':cid,'method':method} for cid,text in sources if (method:=title_match(item['title'],text,normalized=True))]
   if not hits:continue
   if not item['url']:without_link+=len(hits)
   matches.append({'title':item['title'],'url':item['url'],'guid':item['guid'],'artwork':item.get('artwork'),'hits':hits});total+=len(hits)
  if rows or sid not in out:out[sid]={'feed_status':'available' if rows else ('unavailable_or_empty' if sid in jobs else 'no_feed_found'),'items_checked':len(rows),'matches':matches}
 attempted=max(len(jobs),previous.get('feeds_attempted',0) if previous else 0);available=sum(v['feed_status']=='available' for v in out.values());total=sum(len(m['hits']) for v in out.values() for m in v['matches']);without_link=sum(len(m['hits']) for v in out.values() for m in v['matches'] if not m['url'])
 cache.write_text(json.dumps({'shows':out,'feeds_attempted':attempted,'feeds_with_items':available,'title_hits':total,'hits_without_episode_link':without_link,'duplicate_titles_skipped':collisions},ensure_ascii=False))
 print('RSS attempted:',attempted,'with items:',available,'title hits:',total,'without episode link:',without_link,flush=True)
if __name__=='__main__':main()
