#!/usr/bin/env python3
"""Resolve explicit Apple podcast IDs and unambiguous show domains; discard uncertain matches."""
import concurrent.futures as cf, datetime, html, ipaddress, json, re, socket, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path
VERSION='2.0.0'
RAW=Path('data/raw.json'); OUT=Path('dist/data.json')
SHOWS={'99percentinvisible.org':'99% Invisible','lexfridman.com':'Lex Fridman Podcast','acquired.fm':'Acquired','dwarkesh.com':'The Dwarkesh Podcast','softwareengineeringdaily.com':'Software Engineering Daily','radiolab.org':'Radiolab','thisamericanlife.org':'This American Life','se-radio.net':'Software Engineering Radio','econtalk.org':'EconTalk','darknetdiaries.com':'Darknet Diaries','corecursive.com':'CoRecursive'}
def request(url,limit=2_000_000):
    req=urllib.request.Request(url,headers={'User-Agent':'HackerPodcast/2.0','Accept':'application/json, application/rss+xml, application/xml, text/xml, */*'})
    with urllib.request.urlopen(req,timeout=9) as r:
        body=r.read(limit+1)
        if len(body)>limit: raise ValueError('response too large')
        return body

def get_json(url):
    for attempt in range(3):
        try:return json.loads(request(url))
        except (OSError,ValueError):
            if attempt==2:raise
            time.sleep(2**attempt)

def normalized(s):return re.sub(r'[^a-z0-9]+','',s.lower())
def safe(url):
    try:
        p=urllib.parse.urlsplit(url)
        if p.scheme!='https' or not p.hostname or p.username or p.password or p.port not in (None,443):return False
        addresses=socket.getaddrinfo(p.hostname,443,type=socket.SOCK_STREAM)
        return bool(addresses) and all(ipaddress.ip_address(a[4][0]).is_global for a in addresses)
    except Exception:return False

def rss(url):
    if not safe(url):return None
    # No redirects: validate the actual fetch target, not just the initial URL.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs): return None
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'HackerPodcast/2.0'})
        with urllib.request.build_opener(NoRedirect).open(req,timeout=9) as r: data=r.read(2_000_001)
        if len(data)>2_000_000:return None
        root=ET.fromstring(data); channel=root.find('channel')
        if channel is None: channel=root
        def txt(el,name):
            x=el.find(name);return (''.join(x.itertext()).strip() if x is not None else '')
        desc=re.sub(r'\s+',' ',re.sub(r'<[^>]*>',' ',html.unescape(txt(channel,'description')))).strip()[:500]
        item=channel.find('item')
        if item is None:item=channel.find('{http://www.w3.org/2005/Atom}entry')
        latest=None
        if item is not None:
            t=txt(item,'title') or txt(item,'{http://www.w3.org/2005/Atom}title')
            latest={'title':t[:250],'published':txt(item,'pubDate') or txt(item,'{http://www.w3.org/2005/Atom}updated')}
        return {'description':desc,'latest_episode':latest}
    except Exception:return None

def main():
    raw=json.loads(RAW.read_text()); rows=raw['items']; ids={}; names={}
    previous={str(item['id']):item for item in json.loads(OUT.read_text()).get('items',[])} if OUT.exists() else {}
    for item in rows:
        u=urllib.parse.urlsplit(item['url']);host=(u.hostname or '').removeprefix('www.');m=re.search(r'/id(\d+)',u.path)
        if host=='podcasts.apple.com' and m: ids.setdefault(m.group(1),[]).append(item)
        elif host in SHOWS: names.setdefault(SHOWS[host],[]).append(item)
    metadata={}; errors=0
    # Lookup direct IDs in batches; only accept explicit podcast entities.
    for start in range(0,len(ids),20):
        batch=list(ids)[start:start+20]
        try:
            data=get_json('https://itunes.apple.com/lookup?entity=podcast&id='+','.join(batch))
            for x in data.get('results',[]):
                if x.get('kind')=='podcast' and str(x.get('collectionId')) in ids: metadata[str(x['collectionId'])]=x
        except Exception as e:
            print('lookup failed',type(e).__name__,flush=True); errors+=1
        time.sleep(1)
    by_name={normalized(x.get('collectionName','')):x for x in metadata.values()}
    for name in names:
        key=normalized(name)
        if key in by_name:continue
        try:
            url='https://itunes.apple.com/search?'+urllib.parse.urlencode({'term':name,'entity':'podcast','limit':10})
            candidates=get_json(url).get('results',[])
            # No fuzzy match: a wrong show is worse than an omitted show.
            match=next((x for x in candidates if normalized(x.get('collectionName',''))==key and x.get('kind')=='podcast'),None)
            if match:by_name[key]=match
        except Exception as e:
            print('search failed',name,type(e).__name__,flush=True); errors+=1
        time.sleep(1)
    if errors: raise SystemExit('Metadata requests failed; preserving previous published snapshot')
    grouped={}
    def add(meta,rows):
        ident=str(meta['collectionId']); entry=grouped.setdefault(ident,{'id':ident,'title':meta.get('collectionName',''),'artist':meta.get('artistName',''),'artwork':meta.get('artworkUrl600') or meta.get('artworkUrl100'),'feed_url':meta.get('feedUrl'),'url':meta.get('collectionViewUrl'),'genres':meta.get('genres',[]),'track_count':meta.get('trackCount'),'sources':[],'description':'','latest_episode':None})
        # iTunes currently supplies a description as the artist for this show.
        if ident=='1737037853' and entry.get('artist')=='Readings of great articles in AI voices':entry['artist']='Askwho Casts AI'
        for row in rows:entry['sources']+=row['sources']
    for ident,meta in metadata.items():add(meta,ids[ident])
    for name,found in names.items():
        if normalized(name) in by_name:add(by_name[normalized(name)],found)
    entries=[]
    for item in grouped.values():
        unique={s['id']:s for s in item['sources']}; item['sources']=list(unique.values());item['recommendation_count']=len(unique)
        item['created_at']=max((s.get('date') or '' for s in item['sources']),default='')
        # This exact show URL has already been verified by earlier Spotify passes.
        old=previous.get(item['id'],{})
        if old.get('spotify_url'):item['spotify_url']=old['spotify_url']
        if item['title'] and item['url'] and item['sources']:entries.append(item)
    print('resolved',len(entries),'unique shows; fetching RSS',flush=True)
    with cf.ThreadPoolExecutor(max_workers=8) as pool:
        for e in entries:
            feed=e.get('feed_url') or ''
            if feed.startswith('http://'):e['feed_url']='https://'+feed[len('http://'):]
        futures={pool.submit(rss,e.get('feed_url') or ''):e for e in entries}
        for f in cf.as_completed(futures):
            info=f.result()
            if info:futures[f].update(info)
            else:
                # A temporary RSS outage must not erase the last successful result.
                entry=futures[f]; old=previous.get(entry['id'],{})
                entry['feed_url']=old.get('feed_url')
                entry['description']=old.get('description','')
                entry['latest_episode']=old.get('latest_episode')
    if not entries: raise SystemExit('No resolved shows; preserving previous snapshot')
    entries.sort(key=lambda x:(-x['recommendation_count'],x['title'].lower()))
    result={'version':VERSION,'updated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'queries':raw['queries'],'pages_per_query':raw['pages_per_query'],'scanned_unique_comments':raw['scanned_unique_comments'],'matched_comments':raw.get('matched_comments'),'items':entries}
    for key in ('source','source_cutoff_id','source_latest_comment_time','coverage','candidate_comments','partitions_verified'):
        if key in raw:result[key]=raw[key]
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)); archive=Path('snapshots');archive.mkdir(exist_ok=True);(archive/(result['updated_at'][:10]+'.json')).write_text(json.dumps(result,ensure_ascii=False))
    print('saved',len(entries),'shows;',sum(bool(x['description']) for x in entries),'RSS descriptions',flush=True)
if __name__=='__main__':main()
