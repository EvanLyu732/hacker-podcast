#!/usr/bin/env python3
"""Classify Apple episode candidates that did not pass the exact-ID check."""
import concurrent.futures as cf,html,json,re,urllib.error,urllib.parse
from pathlib import Path
from episode_coverage import apple_candidates,AppleMeta
from catalog_enrich import fetch,good_title,image_url

def diagnose(job):
 (sid,eid),item=job
 try:
  raw,final=fetch(item['url'],4_000_000);p=AppleMeta();p.feed(raw.decode('utf8','replace'));u=urllib.parse.urlsplit(p.canonical or final);m=re.search(r'/id(\d+)',u.path);ep=urllib.parse.parse_qs(u.query).get('i',[''])[0];content=p.meta.get('apple:content_id','');title=html.unescape(p.meta.get('og:title','')).strip()
  if m and m.group(1)==sid and ep==eid and content==eid and good_title(title):return (sid,eid),{'verified':{'title':title,'url':p.canonical or final,'artwork':image_url(p.meta.get('og:image',''))}}
  if content==sid or not ep:return (sid,eid),{'reason':'Apple 页面返回节目首页，没有可验证的单集信息'}
  if not good_title(title):return (sid,eid),{'reason':'Apple 单集标题缺失或不够可靠'}
  return (sid,eid),{'reason':'Apple 页面上的节目或单集 ID 与原链接不一致'}
 except urllib.error.HTTPError as e:return (sid,eid),{'reason':f'Apple 页面请求返回 HTTP {e.code}，暂时无法核验'}
 except Exception:return (sid,eid),{'reason':'Apple 页面请求失败或超时，暂时无法核验'}

def main():
 shows=json.loads(Path('dist/data.json').read_text())['items'];raw=json.loads(Path('data/hn_comments.json').read_text());jobs=apple_candidates(shows,raw);cache_path=Path('data/apple_episode_cache.json');cache=json.loads(cache_path.read_text());todo=[j for j in jobs.items() if '|'.join(j[0]) not in cache];failures={}
 with cf.ThreadPoolExecutor(max_workers=3) as pool:
  for ident,result in pool.map(diagnose,todo):
   k='|'.join(ident)
   if result.get('verified'):cache[k]=result['verified']
   else:failures[k]=result['reason']
 cache_path.write_text(json.dumps(cache,ensure_ascii=False,indent=2));Path('data/apple_failure_reasons.json').write_text(json.dumps(failures,ensure_ascii=False,indent=2));print('Apple additional verified:',len(todo)-len(failures),'remaining:',len(failures),flush=True)
if __name__=='__main__':main()
