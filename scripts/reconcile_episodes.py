#!/usr/bin/env python3
"""Join verified direct episode links and conservative RSS title matches to comments."""
import datetime,html,json,re,sys,urllib.parse
from collections import Counter
from pathlib import Path
from catalog_enrich import key,words,title_clean,good_title,merge_verified_aliases
from episode_coverage import apple_candidates
from details import Parse

def identity_apple(url):
 try:
  p=urllib.parse.urlsplit(html.unescape(url));m=re.search(r'/id(\d+)',p.path);eid=urllib.parse.parse_qs(p.query).get('i',[''])[0]
  return (m.group(1),eid) if p.hostname=='podcasts.apple.com' and m and eid.isdigit() else None
 except ValueError:return None

def is_show_title_only(proof,show_name):
 return proof.get('method')=='rss_title' and words(title_clean(proof.get('title','')))==words(title_clean(show_name))

def confirmed_existing_rss_alias(title,hits,entries,raw):
 """Recognize a short RSS title only when every comment links the same episode."""
 short=title_clean(title).strip()
 if not short or not hits:return False
 matches=[]
 for entry in entries:
  full=title_clean(entry['title']).strip()
  if not full.casefold().startswith(short.casefold()):continue
  suffix=full[len(short):]
  if not re.match(r'^\s*(?::|&|[-–—])',suffix):continue
  if not set(map(str,hits))<=set(map(str,entry.get('source_ids',[]))):continue
  valid=True
  for cid in hits:
   parser=Parse();parser.feed(raw.get(str(cid),''))
   if not any(key(link)==key(entry['url']) for link in parser.links):valid=False;break
  if valid:matches.append(entry)
 return len(matches)==1

def main():
 data=json.loads(Path('dist/data.json').read_text());p=Path('dist/details.json');d=json.loads(p.read_text());raw=json.loads(Path('data/hn_comments.json').read_text());apple=json.loads(Path('data/apple_episode_cache.json').read_text());failure_path=Path('data/apple_failure_reasons.json');apple_failures=json.loads(failure_path.read_text()) if failure_path.exists() else {};rss=json.loads(Path('data/rss_match_candidates.json').read_text());spotify=json.loads(Path('data/spotify_episode_candidates.json').read_text());shows={s['id']:s for s in data['items']};jobs=apple_candidates(data['items'],raw)
 before={sid for sid,es in d['episodes'].items() if es};prior_path=Path('dist/episode-audit.json');prior=json.loads(prior_path.read_text()) if prior_path.exists() else {};same_snapshot=prior and prior.get('data_snapshot',data['updated_at'])==data['updated_at'];baseline=prior.get('scope',{}).get('initial_shows_with_episodes',len(before)) if same_snapshot else len(before);initial_associations={(sid,cid,e['url']) for sid,es in d['episodes'].items() for e in es for cid in e['source_ids']};events=Counter();unresolved=[]
 # A show name appearing in a comment does not by itself prove an episode mention.
 for sid,entries in list(d['episodes'].items()):
  retained=[];show_name=words(title_clean(shows[sid]['title']))
  for entry in entries:
   for cid in list(entry.get('source_ids',[])):
    proofs=entry.get('evidence',{}).get(cid,[])
    filtered=[proof for proof in proofs if not is_show_title_only(proof,show_name)]
    if len(filtered)!=len(proofs):
     events['incorrect_show_title_matches_removed']+=1
     if filtered:entry['evidence'][cid]=filtered
     else:entry.get('evidence',{}).pop(cid,None);entry['source_ids'].remove(cid)
   if entry.get('source_ids'):
    entry['source_id']=entry['source_ids'][0];retained.append(entry)
  d['episodes'][sid]=retained
 def match_title(sid,title):
  return [e for e in d['episodes'].get(sid,[]) if words(title_clean(e['title']))==words(title_clean(title))]
 def rss_corroborates(sid,title):
  return any(words(title_clean(m['title']))==words(title_clean(title)) for m in rss['shows'].get(sid,{}).get('matches',[]))
 def find_existing(sid,title,url,source_ids):
  es=d['episodes'].setdefault(sid,[]);apple_id=identity_apple(url)
  direct=[e for e in es if key(e['url'])==key(url) or (apple_id and identity_apple(e['url'])==apple_id)]
  if len(direct)==1:return direct[0],None
  title_matches=match_title(sid,title)
  if len(title_matches)==1:
   e=title_matches[0]
   if set(source_ids)&set(e['source_ids']) or rss_corroborates(sid,title):return e,None
   return None,'同节目存在同名单集，但缺少可核验的跨平台身份，未合并'
  if len(title_matches)>1:return None,'同节目存在多个同名单集，无法确认对应版本'
  return None,None
 def attach(sid,title,url,artwork,evidence,method):
  if not good_title(title) or not url:return
  ids=list(evidence);entry,ambiguous=find_existing(sid,title,url,ids)
  if ambiguous:
   unresolved.append({'show':shows[sid]['title'],'show_id':sid,'episode_title':title,'episode_url':url,'comment_ids':ids,'reason':ambiguous});events['ambiguous']+=1;return
  if entry is None:
   entry={'title':title,'url':url,'source_id':ids[0],'source_ids':[],'evidence':{}}
   if artwork:entry.update(artwork=artwork,artwork_source=method)
   d['episodes'].setdefault(sid,[]).append(entry);events['new_episode']+=1
  elif artwork and not entry.get('artwork'):entry.update(artwork=artwork,artwork_source=method)
  for cid,proofs in evidence.items():
   if cid not in entry['source_ids']:entry['source_ids'].append(cid);events['new_association']+=1
   target=entry.setdefault('evidence',{}).setdefault(cid,[])
   for proof in proofs:
    if proof not in target:target.append(proof)
  entry['source_ids']=sorted(entry['source_ids']);entry['source_id']=entry['source_ids'][0]
 for (sid,eid),item in jobs.items():
  meta=apple.get(sid+'|'+eid)
  if not meta:
   unresolved.append({'show':shows[sid]['title'],'show_id':sid,'episode_url':item['url'],'comment_ids':list(item['sources']),'reason':apple_failures.get(sid+'|'+eid,'Apple 单集页面未能验证：页面不可用、返回节目首页或标题不可靠')});events['apple_unverified']+=1;continue
  evidence={cid:[{'method':'link','url':link} for link in dict.fromkeys(links)] for cid,links in item['sources'].items()}
  attach(sid,meta['title'],meta['url'],meta.get('artwork'),evidence,'apple_episode')
 for k,item in spotify['candidates'].items():
  sid,eid=k.split('|',1);evidence={cid:[{'method':'link','url':link} for link in dict.fromkeys(links)] for cid,links in item['sources'].items()};attach(sid,item['title'],item['url'],item.get('artwork'),evidence,'spotify_episode')
 for item in spotify['failed']:
  unresolved.append(dict(item,episode_url='https://open.spotify.com/episode/'+item['episode_id']))
 for sid,record in rss['shows'].items():
  for item in record['matches']:
   title=item['title']
   if words(title_clean(title))==words(title_clean(shows[sid]['title'])):continue
   hits=[h['id'] for h in item['hits']];existing=match_title(sid,title)
   if not item['url'] and not existing and confirmed_existing_rss_alias(title,hits,d['episodes'].get(sid,[]),raw):
    events['already_linked_rss_alias']+=1;continue
   if not item['url'] and len(existing)!=1:
    unresolved.append({'show':shows[sid]['title'],'show_id':sid,'episode_title':title,'comment_ids':hits,'reason':'RSS 匹配到标题，但未提供可用的单集链接'});events['rss_no_link']+=1;continue
   if len(existing)>1:
    unresolved.append({'show':shows[sid]['title'],'show_id':sid,'episode_title':title,'comment_ids':hits,'reason':'RSS 标题对应多个节目版本，无法确定具体单集'});events['ambiguous']+=1;continue
   url=item['url'] or existing[0]['url'];proof={h['id']:[{'method':'rss_title','title':title}] for h in item['hits']};attach(sid,title,url,item.get('artwork'),proof,'rss')
 for sid,rows in d['episodes'].items():d['episodes'][sid]=merge_verified_aliases(rows)
 d['episodes']={sid:es for sid,es in d['episodes'].items() if es};p.write_text(json.dumps(d,ensure_ascii=False,indent=2))
 # Every source is checked; unlinked comments are only possible omissions, not asserted episode mentions.
 all_sources=0;associated=0;possible=[];missing_feeds=[]
 for sid,show in shows.items():
  linked={cid for e in d['episodes'].get(sid,[]) for cid in e['source_ids']};all_sources+=len(show['sources']);associated+=sum(str(s['id']) in linked for s in show['sources'])
  feed=rss['shows'].get(sid,{});
  if feed.get('feed_status')!='available':missing_feeds.append({'show':show['title'],'show_id':sid,'reason':'RSS 未获取、无有效单集或没有找到 RSS'})
  for src in show['sources']:
   cid=str(src['id']);text=html.unescape(re.sub('<[^>]+>',' ',raw.get(cid,src.get('text',''))));text=re.sub(r'\s+',' ',text).strip()
   if cid not in linked and re.search(r'\b(?:episode|episodes|ep\.?\s*\d+|interview)\b',text,re.I):
    possible.append({'show':show['title'],'show_id':sid,'comment_id':cid,'comment_url':'https://news.ycombinator.com/item?id='+cid,'excerpt':text[:240],'reason':'评论提到单集或访谈，但尚未找到可确认的单集身份'})
 if same_snapshot:
  for name in ('new_episode','new_association','incorrect_show_title_matches_removed'):events[name]+=prior.get('changes',{}).get(name,0)
 report={'generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'data_snapshot':data['updated_at'],'scope':{'shows':len(shows),'source_references':all_sources,'distinct_source_comments':len({str(s['id']) for show in shows.values() for s in show['sources']}),'initial_shows_with_episodes':baseline,'shows_with_episodes':len(d['episodes']),'episodes':sum(map(len,d['episodes'].values())),'source_references_associated':associated,'apple_episode_candidates':len(jobs),'apple_verified_pages':sum('|'.join(k) in apple for k in jobs),'spotify_candidates':spotify['total'],'spotify_verified':len(spotify['candidates']),'rss_feeds_attempted':rss['feeds_attempted'],'rss_feeds_with_items':rss['feeds_with_items'],'rss_title_hits':rss['title_hits']},'changes':dict(events),'unresolved':unresolved,'possible_unlinked_comments':possible,'unavailable_rss':missing_feeds}
 Path('dist/episode-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
 lines=['# 单集关联核查清单','',f"生成时间（UTC）：{report['generated_at']}",'',f"范围：{len(shows)} 个现有节目、{all_sources} 条节目评论引用；按 HN 评论直接链接和可用 RSS 标题核查。",'',f"核查结果：{len(d['episodes'])} 个节目有 {sum(map(len,d['episodes'].values()))} 期可核实单集；未核实并不代表评论一定提及单集。",'',f"## 有具体候选但暂未确认（{len(unresolved)} 项）",'']
 for item in unresolved:
  name=item.get('show','');title=item.get('episode_title') or item.get('episode_url') or item.get('episode_id','');ids=item.get('comment_ids',[]);links=' '.join(f'[HN {cid}](https://news.ycombinator.com/item?id={cid})' for cid in ids);lines.append(f"- **{name}** — {title}；{item['reason']}。{links}")
 lines += ['',f"## 待人工核查的评论（{len(possible)} 条）",'', '这些评论包含“episode”或“interview”等词，但尚未确认单集；其中可能只是泛泛讨论，并非已证实的遗漏。','']
 for item in possible:lines.append(f"- **{item['show']}** — [HN {item['comment_id']}]({item['comment_url']})：{item['excerpt'].replace(chr(10),' ')}")
 lines += ['',f"## RSS 未获取或没有有效单集（{len(missing_feeds)} 个节目）",'', '可能是暂时不可达、数据源返回空结果或没有找到 RSS；不表示这些节目没有单集。','']
 for item in missing_feeds:lines.append(f"- {item['show']}")
 Path('dist/episode-audit.md').write_text('\n'.join(lines)+'\n');print('Report:',json.dumps(report['scope'],ensure_ascii=False),'changes:',dict(events),'unresolved:',len(unresolved),'possible:',len(possible),'unavailable RSS:',len(missing_feeds),flush=True)
if __name__=='__main__':main()
