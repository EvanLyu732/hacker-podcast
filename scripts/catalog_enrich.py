#!/usr/bin/env python3
"""Conservatively match RSS episode titles and verified Spotify show pages."""
import concurrent.futures as cf, html, json, re, time, unicodedata, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from html.parser import HTMLParser
from enrich import safe
from episode_artwork import image_url,image_key

ITUNES='{http://www.itunes.com/dtds/podcast-1.0.dtd}'
MEDIA='{http://search.yahoo.com/mrss/}'
NOISE=re.compile(r'^(?:dawgyg|(?:podcast\s*)?episode(?:\s*#?\d+)?|podcast|untitled(?:\s*episode)?|unknown|home|404|not found)$',re.I)
class SafeRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):
  if not safe(newurl):raise ValueError('unsafe redirect')
  return super().redirect_request(req,fp,code,msg,headers,newurl)
def fetch(url,limit=8_000_000):
 if not safe(url):raise ValueError('unsafe URL')
 req=urllib.request.Request(url,headers={'User-Agent':'HackerPodcast/2.3','Accept':'application/json,application/rss+xml,application/xml,text/xml,text/html,*/*'})
 with urllib.request.build_opener(SafeRedirect).open(req,timeout=12) as response:
  body=response.read(limit+1)
  if len(body)>limit:raise ValueError('response too large')
  return body,response.geturl()
def words(s):return ' '.join(re.findall(r'[^\W_]+',unicodedata.normalize('NFKC',html.unescape(s or '')).casefold()))
def key(s):
 try:
  p=urllib.parse.urlsplit(html.unescape(s or ''));host=(p.hostname or '').lower().removeprefix('www.');path=urllib.parse.unquote(p.path).rstrip('/');episode=urllib.parse.parse_qs(p.query).get('i',[''])[0] if host=='podcasts.apple.com' else ''
  return (host,path,episode)
 except ValueError:return ('','','')
def guid_key(value):
 # RSS GUIDs are opaque identities: their query parameters must never be discarded.
 value=html.unescape(value or '').strip()
 try:
  p=urllib.parse.urlsplit(value)
  if p.scheme in ('http','https') and p.hostname:
   return ('url',p.hostname.lower().removeprefix('www.'),p.path.rstrip('/'),p.query)
 except ValueError:pass
 return ('opaque',value)
def title_clean(t):return re.sub(r'\s+[-|–—]\s+(?:Econlib|99% Invisible|Darknet Diaries|Acquired|Radiolab|This American Life)\s*$', '',html.unescape(t or ''),flags=re.I).strip()
def good_title(t):
 t=title_clean(t)
 return bool(len(t)>=5 and len(words(t))>=5 and not NOISE.fullmatch(t) and not re.fullmatch(r'[\W\d_]+',t) and not re.match(r'^(?:access denied|just a moment|404|page not found)\b',t,re.I))
def parse_rss(url):
 try:
  body,final=fetch(url);root=ET.fromstring(body);entries=[];showlinks=[]
  channel=root.find('channel');channel_art=None
  if channel is not None:
   image=channel.find(ITUNES+'image');channel_art=image_url(image.get('href') if image is not None else '',final)
   if not channel_art:channel_art=image_url(channel.findtext('./image/url') or '',final)
  for node in root.findall('./channel/link'):
   if node.text:showlinks.append(node.text.strip())
  for i in root.findall('./channel/item'):
   title=html.unescape(i.findtext('title') or '').strip();link=(i.findtext('link') or '').strip();guid=(i.findtext('guid') or '').strip()
   if not good_title(title):continue
   # Generic channel/homepage links are not playable episode links.
   parsed=urllib.parse.urlsplit(link);u=link if parsed.scheme in ('https','http') and parsed.path not in ('','/') else ''
   if u.startswith('http://'):u='https://'+u[7:]
   artwork=i.find(ITUNES+'image');art=artwork.get('href') if artwork is not None else None
   if not art:
    artwork=i.find(MEDIA+'thumbnail');art=artwork.get('url') if artwork is not None else None
   if not art:
    artwork=i.find(MEDIA+'content');art=artwork.get('url') if artwork is not None and (artwork.get('medium')=='image' or (artwork.get('type') or '').startswith('image/')) else None
   art=image_url(art,final)
   if art and channel_art and image_key(art)==image_key(channel_art):art=None
   entries.append({'title':title,'url':u,'guid':guid,'artwork':art})
  return entries,showlinks
 except Exception:return [],[]
def final_key(url):
 try:
  if urllib.parse.urlsplit(url).hostname not in ('www.econtalk.org','99percentinvisible.org','darknetdiaries.com','acquired.fm','radiolab.org','thisamericanlife.org'):return key(url)
  _,final=fetch(url,2_500_000);result=key(final);return result if result[1] else key(url)
 except Exception:return key(url)
class ShowMeta(HTMLParser):
 def __init__(self):super().__init__();self.title=''
 def handle_starttag(self,tag,attrs):
  d=dict(attrs)
  if tag=='meta' and d.get('property')=='og:title':self.title=d.get('content','')
def oembed(url):
 # Spotify show oEmbed can describe the latest episode; use the public show page title instead.
 try:
  raw,_=fetch(url,3_000_000);p=ShowMeta();p.feed(raw.decode('utf8','replace'));return url,html.unescape(p.title)
 except Exception:return url,''
# These two official Radiolab pages have the same episode title and description;
# the later page is a re-release. Keep source links in per-comment evidence.
VERIFIED_ALIASES={key('https://radiolab.org/podcast/americanish-2306'):key('https://radiolab.org/podcast/americanish')}
def merge_verified_aliases(items):
 out=[];index={}
 for e in items:
  identity=VERIFIED_ALIASES.get(key(e['url']),key(e['url']))
  if identity not in index:
   index[identity]=e;out.append(e);continue
  target=index[identity];target['source_ids']=sorted(set(target['source_ids'])|set(e['source_ids']));target['source_id']=target['source_ids'][0]
  for cid,entries in e.get('evidence',{}).items():
   arr=target.setdefault('evidence',{}).setdefault(cid,[])
   for entry in entries:
    if entry not in arr:arr.append(entry)
  if not target.get('artwork') and e.get('artwork'):target['artwork']=e['artwork'];target['artwork_source']=e.get('artwork_source','episode_page')
 return out
def itunes_feeds(shows):
 ids=[s['id'] for s in shows if not s.get('feed_url')];out={}
 for n in range(0,len(ids),20):
  try:
   raw,_=fetch('https://itunes.apple.com/lookup?entity=podcast&id='+','.join(ids[n:n+20]),2_000_000)
   for item in json.loads(raw).get('results',[]):
    if item.get('kind')=='podcast' and item.get('feedUrl'):out[str(item['collectionId'])]=item['feedUrl']
  except Exception:pass
  time.sleep(.3)
 return out

def main():
 data_path=Path('dist/data.json');details_path=Path('dist/details.json');data=json.loads(data_path.read_text());detail=json.loads(details_path.read_text());raw=json.loads(Path('data/raw.json').read_text());comments=json.loads(Path('data/hn_comments.json').read_text());shows=data['items'];feeds=itunes_feeds(shows)
 raw_spotify={r['url'] for r in raw['items'] if re.fullmatch(r'https?://open\.spotify\.com/show/[A-Za-z0-9]+/?',r['url'])}
 # Exact Spotify show names are verified against the public Spotify show page. Ambiguous names are omitted.
 with cf.ThreadPoolExecutor(max_workers=8) as pool:
  spotify=list(pool.map(oembed,sorted(raw_spotify)))
  rssjobs={s['id']:pool.submit(parse_rss,s.get('feed_url') or feeds.get(s['id'])) for s in shows if s.get('feed_url') or feeds.get(s['id'])}
  finaljobs={}
  for sid,items in detail['episodes'].items():
   duplicate_titles=Counter(words(title_clean(e['title'])) for e in items)
   for e in items:
    if duplicate_titles[words(title_clean(e['title']))]>1:finaljobs[(sid,e['url'])]=pool.submit(final_key,e['url'])
  rss={sid:f.result() for sid,f in rssjobs.items()};final={k:f.result() for k,f in finaljobs.items()}
 successful_feeds=sum(bool(v[0]) for v in rss.values())
 print('RSS feeds usable:',successful_feeds,'/',len(rssjobs),flush=True)
 if not rssjobs or successful_feeds < max(1,int(len(rssjobs)*.2)):
  raise SystemExit('Too many RSS feeds unavailable; do not publish this refresh')
 names=defaultdict(list);by_id={x['id']:x for x in shows}
 for s in shows:names[words(s['title'])].append(s)
 matches=defaultdict(set)
 for link,title in spotify:
  n=words(title)
  if len(names[n])==1:matches[names[n][0]['id']].add(link.rstrip('/'))
 for s in shows:
  if s.get('spotify_url'):matches[s['id']].add(s['spotify_url'])
  s.pop('spotify_url',None)
  if len(matches[s['id']])==1:s['spotify_url']=next(iter(matches[s['id']]))
 # Match an RSS title only when unique within that show, sufficiently distinctive, and literally present in a source comment.
 removed=added=merged=0
 for show in shows:
  sid=show['id'];old=detail['episodes'].get(sid,[]);rows,_=rss.get(sid,([],[]));tally=Counter(words(x['title']) for x in rows);rss_unique={words(x['title']):x for x in rows if tally[words(x['title'])]==1};merged_by={};alias={}
  def put(e,identity):
   nonlocal merged
   ids=set(map(str,e.get('source_ids',[e.get('source_id')])));ids.discard('None')
   evidence=e.get('evidence') or {cid:[{'method':'link','url':e['url']}] for cid in ids}
   if identity in merged_by:
    existing=merged_by[identity];existing['source_ids']=sorted(set(existing['source_ids'])|ids);merged+=1
    for cid,items in evidence.items():
     target=existing.setdefault('evidence',{}).setdefault(cid,[])
     for item in items:
      if item not in target:target.append(item)
    if not existing.get('artwork') and e.get('artwork'):existing['artwork']=e['artwork'];existing['artwork_source']=e.get('artwork_source','rss')
   else:
    e=dict(e);e['source_ids']=sorted(ids);e['source_id']=e['source_ids'][0] if e['source_ids'] else '';e['evidence']=evidence;merged_by[identity]=e
  for e in old:
   if not good_title(e['title']):removed+=1;continue
   normalized=words(title_clean(e['title']));match=rss_unique.get(normalized);fk=final.get((sid,e['url']),key(e['url']))
   identity=('url',fk)
   # An exact, unique RSS title maps aliases to the RSS GUID/link. Do not merge ambiguous titles.
   if match:identity=('rss',guid_key(match['guid']) if match['guid'] else key(match['url']) if match['url'] else fk)
   alias[key(e['url'])]=identity
   if match:
    if match['url']:alias[key(match['url'])]=identity
    if match.get('artwork'):e=dict(e,artwork=match['artwork'],artwork_source='rss')
   put(e,identity)
  normalized_comments=[(str(source['id']), ' '+words(re.sub('<[^>]*>',' ',comments.get(str(source['id']),source.get('text',''))))+' ') for source in show['sources']]
  for item in rows:
   name=words(item['title']);tokens=name.split()
   if not item['url'] or tally[name]!=1 or len(name)<20 or len(tokens)<4 or len(set(tokens))<3:continue
   hits=[cid for cid,text in normalized_comments if f' {name} ' in text]
   if not hits:continue
   identity=alias.get(key(item['url'])) or ('rss',guid_key(item['guid']) if item['guid'] else key(item['url']))
   e={'title':item['title'],'url':item['url'],'source_id':hits[0],'source_ids':hits,'evidence':{cid:[{'method':'rss_title','title':item['title']}] for cid in hits}}
   if item.get('artwork'):e.update(artwork=item['artwork'],artwork_source='rss')
   if identity not in merged_by:added+=1
   put(e,identity)
  detail['episodes'][sid]=merge_verified_aliases(list(merged_by.values()))
 detail['episodes']={sid:rows for sid,rows in detail['episodes'].items() if rows}
 data_path.write_text(json.dumps(data,ensure_ascii=False,indent=2));details_path.write_text(json.dumps(detail,ensure_ascii=False,indent=2))
 print('RSS feeds read:',sum(bool(v[0]) for v in rss.values()),'Spotify exact matches:',sum('spotify_url' in x for x in shows),'removed noise:',removed,'merged:',merged,'new RSS episodes:',added,'total episodes:',sum(map(len,detail['episodes'].values())),'shows with episodes:',len(detail['episodes']))
if __name__=='__main__':main()
