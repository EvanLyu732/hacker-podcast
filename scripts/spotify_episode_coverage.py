#!/usr/bin/env python3
"""Resolve explicit Spotify episode links only when the parent show is verified."""
import concurrent.futures as cf,html,json,re,urllib.parse
from collections import Counter
from pathlib import Path
from details import Parse
from catalog_enrich import fetch,oembed,words,good_title,image_url
from episode_coverage import AppleMeta

def resolve(item):
 try:
  raw,_=fetch(item['url'],3_000_000);text=raw.decode('utf8','replace');p=AppleMeta();p.feed(text);m=re.search(r'</h1>\s*<a[^>]*href="/show/([A-Za-z0-9]+)"',text)
  title=html.unescape(p.meta.get('og:title','')).strip()
  if not m or not good_title(title):return None
  parent='https://open.spotify.com/show/'+m.group(1);return {'title':title,'parent':parent,'artwork':image_url(p.meta.get('og:image',''))}
 except Exception:return None

def main():
 shows=json.loads(Path('dist/data.json').read_text())['items'];raw=json.loads(Path('data/hn_comments.json').read_text());titles=Counter(words(s['title']) for s in shows);jobs={}
 for show in shows:
  for src in show['sources']:
   cid=str(src['id']);p=Parse();p.feed(raw.get(cid,''))
   for link in p.links:
    try:
     u=urllib.parse.urlsplit(link);m=re.fullmatch(r'/episode/([A-Za-z0-9]+)/?',u.path)
     if u.hostname=='open.spotify.com' and m:
      item=jobs.setdefault((show['id'],m.group(1)),{'url':'https://open.spotify.com/episode/'+m.group(1),'sources':{}});item['sources'].setdefault(cid,[]).append(link)
    except ValueError:pass
 with cf.ThreadPoolExecutor(max_workers=6) as pool:resolved=list(pool.map(lambda j:(j[0],resolve(j[1])),jobs.items()))
 byid={s['id']:s for s in shows};parents={v['parent'] for _,v in resolved if v};
 with cf.ThreadPoolExecutor(max_workers=6) as pool:parent_titles=dict(pool.map(oembed,parents))
 out={};failed=[]
 for ident,meta in resolved:
  sid,eid=ident;item=jobs[ident];show=byid[sid]
  if not meta:failed.append({'show':show['title'],'show_id':sid,'episode_id':eid,'comment_ids':list(item['sources']),'reason':'Spotify 单集页面不可用或标题不可靠'});continue
  parent_title=parent_titles.get(meta['parent'],'');known=show.get('spotify_url','').rstrip('/')
  if not ((known and known==meta['parent']) or (parent_title and words(parent_title)==words(show['title']) and titles[words(show['title'])]==1)):
   failed.append({'show':show['title'],'show_id':sid,'episode_id':eid,'comment_ids':list(item['sources']),'reason':'Spotify 单集所属节目无法与该节目可靠匹配'});continue
  out[sid+'|'+eid]={'title':meta['title'],'url':item['url'],'artwork':meta['artwork'],'sources':item['sources']}
 if len(jobs)>=4 and len(out)<len(jobs)*.5:raise SystemExit('Too few Spotify episode links could be verified; do not publish this refresh')
 Path('data/spotify_episode_candidates.json').write_text(json.dumps({'candidates':out,'failed':failed,'total':len(jobs)},ensure_ascii=False,indent=2))
 print('Spotify episode candidates:',len(jobs),'verified for show:',len(out),'unresolved:',len(failed),flush=True)
if __name__=='__main__':main()
