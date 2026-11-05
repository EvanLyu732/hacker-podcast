#!/usr/bin/env python3
"""Add exact-episode artwork from the show's RSS or its linked episode page."""
import concurrent.futures as cf, html, json, re, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from enrich import safe

ALLOWED={'www.econtalk.org','99percentinvisible.org','darknetdiaries.com','acquired.fm','radiolab.org','thisamericanlife.org','podcasts.apple.com'}
ITUNES='{http://www.itunes.com/dtds/podcast-1.0.dtd}'
MEDIA='{http://search.yahoo.com/mrss/}'
class SafeRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):
  if not safe(newurl):raise ValueError('unsafe redirect')
  return super().redirect_request(req,fp,code,msg,headers,newurl)

def fetch(url,max_bytes,with_url=False):
 if not safe(url):raise ValueError('invalid URL')
 req=urllib.request.Request(url,headers={'User-Agent':'HackerPodcast/2.1.2','Accept':'application/rss+xml,application/xml,text/xml,text/html,*/*'})
 with urllib.request.build_opener(SafeRedirect).open(req,timeout=12) as r:
  data=r.read(max_bytes+1)
  if len(data)>max_bytes:raise ValueError('response too large')
  return (data,r.geturl()) if with_url else data

def image_url(value,base=''):
 try:
  value=html.unescape(value or '').strip()
  if not value:return None
  u=urllib.parse.urlsplit(urllib.parse.urljoin(base,value))
  if u.scheme!='https' or not u.hostname or u.username or u.password or u.port not in (None,443):return None
  return u.geturl()
 except ValueError:return None

def norm_url(url):
 p=urllib.parse.urlsplit(url or '');return ((p.hostname or '').lower().removeprefix('www.'),urllib.parse.unquote(p.path).rstrip('/'),p.query)
def norm_title(t):return re.sub(r'[^a-z0-9]+','',re.sub(r'\s*[-|–—]\s*(?:Econlib|99% Invisible|Darknet Diaries|Acquired|Radiolab|This American Life).*$', '',t or '',flags=re.I).lower())
def image_key(url):
 p=urllib.parse.urlsplit(url or '');return ((p.hostname or '').lower().removeprefix('www.'),re.sub(r'/\d+x\d+[^/]*$','',p.path.rstrip('/')))

def rss_images(url):
 try:
  body,final=fetch(url,8000000,with_url=True);root=ET.fromstring(body);entries=[]
  channel=root.find('channel');channel_image=None
  if channel is not None:
   image=channel.find(ITUNES+'image');channel_image=image_url(image.get('href') if image is not None else '',final)
   if not channel_image:channel_image=image_url(channel.findtext('./image/url') or '',final)
  for item in root.findall('./channel/item'):
   title=item.findtext('title') or '';link=item.findtext('link') or '';guid=item.findtext('guid') or ''
   image=item.find(ITUNES+'image')
   img=(image.get('href') if image is not None else '')
   if not img:
    image=item.find(MEDIA+'thumbnail');img=image.get('url') if image is not None else ''
   if not img:
    image=item.find(MEDIA+'content');img=image.get('url') if image is not None and (image.get('medium')=='image' or (image.get('type') or '').startswith('image/')) else ''
   if not img:
    image=item.find('image');img=(image.findtext('url') or image.get('href') or '') if image is not None else ''
   img=image_url(img,final)
   if img and channel_image and image_key(img)==image_key(channel_image):img=None
   entries.append({'url':norm_url(link),'guid':norm_url(guid),'title':norm_title(title),'artwork':img})
  return entries
 except Exception:return []

class EpisodeMeta(HTMLParser):
 def __init__(self):super().__init__();self.images=[];self.title='';self.title_parts=[];self.in_title=False
 def handle_starttag(self,t,a):
  d=dict(a)
  if t=='meta' and (d.get('property') in ('og:image','og:image:url','og:image:secure_url') or d.get('name') in ('twitter:image','twitter:image:src')) and d.get('content'):
   self.images.append(d['content'])
  if t=='meta' and (d.get('property')=='og:title' or d.get('name')=='twitter:title') and d.get('content') and not self.title:self.title=d['content']
  if t=='title':self.in_title=True
 def handle_endtag(self,t):
  if t=='title':self.in_title=False
 def handle_data(self,data):
  if self.in_title:self.title_parts.append(data)

def page_image(url,expected_title):
 try:
  u=urllib.parse.urlsplit(url)
  if u.hostname not in ALLOWED or u.hostname=='podcasts.apple.com':return None
  body,final=fetch(url,2500000,with_url=True);p=EpisodeMeta();p.feed(body.decode('utf8','replace'))
  if (urllib.parse.urlsplit(final).hostname or '').removeprefix('www.')!=(u.hostname or '').removeprefix('www.'):return None
  expected=norm_title(expected_title);actual=norm_title(p.title or ''.join(p.title_parts))
  if len(expected)<10 or expected!=actual:return None
  return next((v for raw in p.images if (v:=image_url(raw,final))),None)
 except Exception:return None

def main():
 path=Path('dist/details.json');details=json.loads(path.read_text());data=json.loads(Path('dist/data.json').read_text());shows={x['id']:x for x in data['items']}; episodes=details['episodes']
 from catalog_enrich import itunes_feeds
 fallback=itunes_feeds([shows[sid] for sid in episodes if sid in shows and not shows[sid].get('feed_url')])
 # For known sources, pages can contain episode-specific Open Graph art. RSS wins if matched.
 with cf.ThreadPoolExecutor(max_workers=8) as pool:
  rss_futures={sid:pool.submit(rss_images,shows[sid].get('feed_url') or fallback[sid]) for sid in episodes if sid in shows and (shows[sid].get('feed_url') or sid in fallback)}
  page_jobs=[(sid,e,pool.submit(page_image,e['url'],e['title'])) for sid,rows in episodes.items() for e in rows]
  rss={sid:f.result() for sid,f in rss_futures.items()}
  page_art={id(e):f.result() for sid,e,f in page_jobs}
 for sid,rows in episodes.items():
  available=rss.get(sid,[])
  feed_titles=Counter(x['title'] for x in available);episode_titles=Counter(norm_title(e['title']) for e in rows)
  page_counts=Counter(image_key(page_art[id(e)]) for e in rows if page_art.get(id(e)))
  for e in rows:
   by_link=[x for x in available if norm_url(e['url']) in (x['url'],x['guid']) and norm_url(e['url'])[1]]
   title=norm_title(e['title'])
   by_title=[x for x in available if len(title)>=10 and feed_titles[title]==1 and episode_titles[title]==1 and title==x['title']]
   matches=by_link or by_title
   rss_art=matches[0]['artwork'] if len(matches)==1 else None
   show_art=shows.get(sid,{}).get('artwork')
   if not e.get('artwork') and rss_art and (not show_art or image_key(rss_art)!=image_key(show_art)):
    e['artwork']=rss_art;e['artwork_source']='rss'
   elif not e.get('artwork') and page_art.get(id(e)) and page_counts[image_key(page_art[id(e)])]<3 and (not show_art or image_key(page_art[id(e)])!=image_key(show_art)):
    e['artwork']=page_art[id(e)];e['artwork_source']='episode_page'
 path.write_text(json.dumps(details,ensure_ascii=False,indent=2))
 print('Artwork sources:',dict(Counter(e.get('artwork_source','show_fallback') for rows in episodes.values() for e in rows)))
if __name__=='__main__':main()
