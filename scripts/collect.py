#!/usr/bin/env python3
"""Scan the public ClickHouse HN mirror by complete ID partitions.

The scan covers all live comments in a bounded, rolling snapshot, while podcast
extraction remains heuristic and is not an exhaustive recommendation classifier.
"""
import concurrent.futures as cf, datetime, html, json, os, re, tempfile, time
import urllib.request, urllib.parse
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path

ENDPOINT='https://play.clickhouse.com/'
PARTITION=500_000
DOMAINS=('podcasts.apple.com','podcasts.google.com','open.spotify.com','overcast.fm','pca.st','podcasts.youtube.com','podcastaddict.com','podchaser.com','player.fm','feeds.simplecast.com','transistor.fm','buzzsprout.com','libsyn.com','soundcloud.com','99percentinvisible.org','lexfridman.com','changelog.com','acquired.fm','dwarkesh.com','softwaresessions.com','softwareengineeringdaily.com','thetalkshow.fm','astralcodexten.substack.com','radiolab.org','thisamericanlife.org','se-radio.net','econtalk.org','freakonomics.com','darknetdiaries.com','thinkingelixir.com','corecursive.com')
POSITIVE=re.compile(r'\b(recommend|recommended|recommendation|great|excellent|good|enjoyed|enjoy|interesting|worth (?:a )?listen|love|favorite|favourite|best|listen to|listening to|check out|fan of)\b',re.I)
NEGATIVE=re.compile(r'\b(don.t recommend|wouldn.t recommend|not recommend|avoid|terrible|awful|worst|hate)\b',re.I)
TERMS=('podcast',)+DOMAINS
CONDITION='multiSearchAnyCaseInsensitive(text, ['+','.join("'"+t+"'" for t in TERMS)+']) > 0'
BASE="type='comment' AND deleted=0 AND dead=0"
class Links(HTMLParser):
 def __init__(self):super().__init__();self.links=[];self.parts=[];self.current=None
 def handle_starttag(self,tag,attrs):
  if tag=='a':self.current=dict(attrs).get('href');self.parts=[]
 def handle_data(self,data):
  if self.current:self.parts.append(data)
 def handle_endtag(self,tag):
  if tag=='a' and self.current:self.links.append((self.current,''.join(self.parts)));self.current=None

def query(sql):
 url=ENDPOINT+'?'+urllib.parse.urlencode({'user':'play','query':sql+' FORMAT JSONEachRow'})
 for attempt in range(4):
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'HackerPodcast/3.0'})
   with urllib.request.urlopen(req,timeout=90) as response:
    return [json.loads(line) for line in response if line.strip()]
  except (OSError,ValueError) as e:
   if attempt==3:raise RuntimeError('ClickHouse request failed after retries') from e
   time.sleep(2**attempt)

def atomic_json(path,data):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 fd,tmp=tempfile.mkstemp(dir=path.parent,prefix='.hn-scan-')
 try:
  with os.fdopen(fd,'w') as f:json.dump(data,f,ensure_ascii=False,indent=2)
  os.replace(tmp,path)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)

def main():
 boundary=query("SELECT max(id) AS max_id, max(time) AS latest_time FROM hackernews_history FINAL WHERE "+BASE)[0]
 cutoff=int(boundary['max_id']);where=BASE+f' AND id <= {cutoff}'
 counts=query(f'SELECT intDiv(id,{PARTITION}) AS p, count() AS total, countIf({CONDITION}) AS candidates FROM hackernews_history FINAL WHERE {where} GROUP BY p ORDER BY p')
 if not counts or cutoff==0:raise SystemExit('Empty source; old snapshot preserved')
 def download(row):
  part=int(row['p']);lo=part*PARTITION;hi=min((part+1)*PARTITION-1,cutoff)
  records=query(f'SELECT id, by, time, text FROM hackernews_history FINAL WHERE {where} AND id >= {lo} AND id <= {hi} AND {CONDITION}')
  if len(records)!=int(row['candidates']) or len({r['id'] for r in records})!=len(records):raise RuntimeError(f'Partition {part} mismatch; source changed or response incomplete, rerun')
  return part,records
 items={};comments={};matched=set();candidate_total=0
 with cf.ThreadPoolExecutor(max_workers=4) as pool:
  for part,records in pool.map(download,counts):
   candidate_total+=len(records)
   for hit in records:
    cid=str(hit['id']);text=hit.get('text') or '';plain=html.unescape(re.sub('<[^>]+>',' ',text));plain=re.sub(r'\s+',' ',plain).strip()
    if not POSITIVE.search(plain) or NEGATIVE.search(plain):continue
    parser=Links();parser.feed(text)
    for raw,label in parser.links:
     try:
      u=urllib.parse.urlsplit(html.unescape(raw));host=(u.hostname or '').lower().removeprefix('www.')
      if u.scheme not in ('https','http') or not any(host==d or host.endswith('.'+d) for d in DOMAINS):continue
      if host in ('overcast.fm','pca.st','open.spotify.com','podcasts.apple.com','player.fm','podcastaddict.com','podchaser.com','soundcloud.com') and u.path in ('','/'):continue
      if host=='open.spotify.com' and not re.search(r'/(episode|show)/',u.path):continue
      canonical=urllib.parse.urlunsplit((u.scheme,u.netloc,u.path.rstrip('/'),'',''))
      label=html.unescape(label).strip()
      if not label or label.startswith(('http','www.')) or len(label)<5:label=host.replace('podcasts.apple.com','Apple Podcasts').replace('open.spotify.com','Spotify')
      if canonical not in items:items[canonical]={'objectID':cid,'title':label,'url':canonical,'points':0,'num_comments':0,'created_at':hit['time'].replace(' ','T')+'Z','sources':{}}
      item=items[canonical];item['sources'][cid]={'id':cid,'author':hit.get('by',''),'text':plain[:450],'story':'','date':hit['time'].replace(' ','T')+'Z'}
      comments[cid]=text;matched.add(cid)
     except ValueError:continue
   print(f'Checked partition {part}: {len(records)} candidates; {len(matched)} linked comments',flush=True)
 for item in items.values():
  item['sources']=list(item['sources'].values());item['points']=len(item['sources']);item['num_comments']=len(item['sources'])
 total=sum(int(r['total']) for r in counts)
 if not items or candidate_total!=sum(int(r['candidates']) for r in counts):raise SystemExit('Incomplete scan; previous snapshot preserved')
 result={'updated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':'ClickHouse hackernews_history FINAL','source_cutoff_id':cutoff,'source_latest_comment_time':boundary['latest_time']+' UTC','coverage':'All live comments up to cutoff; extraction is heuristic','queries':list(TERMS),'pages_per_query':None,'scanned_unique_comments':total,'candidate_comments':candidate_total,'matched_comments':len(matched),'partitions_verified':len(counts),'items':sorted(items.values(),key=lambda x:-x['points'])}
 atomic_json('data/hn_comments.json',comments);atomic_json('data/raw.json',result)
 print(f'Complete: {total} comments screened, {candidate_total} candidates, {len(matched)} linked comments, {len(items)} URLs',flush=True)
if __name__=='__main__':main()
