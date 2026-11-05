#!/usr/bin/env python3
"""Run a fail-closed, isolated refresh. Publishing is a separate Sites operation."""
import datetime as dt, fcntl, json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

ROOT=Path(__file__).resolve().parents[1]
STEPS=[
 [sys.executable,'scripts/collect.py'],[sys.executable,'scripts/enrich.py'],
 [sys.executable,'scripts/details.py'],[sys.executable,'scripts/episode_artwork.py'],
 [sys.executable,'scripts/catalog_enrich.py'],[sys.executable,'scripts/episode_coverage.py'],
 [sys.executable,'scripts/diagnose_apple_failures.py'],[sys.executable,'scripts/rss_coverage.py'],
 [sys.executable,'scripts/rss_coverage.py','--retry-unavailable'],[sys.executable,'scripts/spotify_episode_coverage.py'],
 [sys.executable,'scripts/reconcile_episodes.py'],[sys.executable,'scripts/audit_catalog.py'],
 [sys.executable,'scripts/spotify_enrich.py'],[sys.executable,'scripts/wikidata_spotify.py'],
 [sys.executable,'-m','unittest','discover','-s','tests','-p','test_*.py'],
 ['node','tests/app.test.js'],['node','tests/episode_views.test.js'],['node','tests/daily_feature.test.js'],['node','tests/share.test.js'],['node','tests/search.test.js'],['node','tests/artwork_referrer.test.js'],['node','tests/sorting.test.js']]
OUTPUTS={'dist':('data.json','details.json','episode-audit.json','episode-audit.md')}
def read_json(path):return json.loads(path.read_text())
def stamp(value):return dt.datetime.fromisoformat(value.replace('Z','+00:00'))
def references(data):return {(str(show['id']),str(src['id'])) for show in data['items'] for src in show['sources']}
def episode_references(details):return {(str(sid),str(cid)) for sid,episodes in details['episodes'].items() for ep in episodes for cid in ep['source_ids']}
def episode_identity(url):
 try:
  p=urlsplit(url or '');host=(p.hostname or '').lower().removeprefix('www.');path=unquote(p.path).rstrip('/')
  if p.scheme not in ('http','https') or not host or not path:return None
  # Preserve non-Apple query strings: they can identify different episodes.
  episode=parse_qs(p.query).get('i',[''])[0] if host=='podcasts.apple.com' else p.query
  return host,path,episode
 except ValueError:return None

def preserve_episode_artwork(old_details,new_details):
 """Keep previously verified episode art when the same URL loses its artwork."""
 restored=0
 for sid,rows in new_details.get('episodes',{}).items():
  old={}
  for e in old_details.get('episodes',{}).get(sid,[]):
   identity=episode_identity(e.get('url'))
   if identity and e.get('artwork'):old.setdefault(identity,[]).append(e)
  for e in rows:
   prior=old.get(episode_identity(e.get('url')),[])
   if not e.get('artwork') and len(prior)==1:
    e['artwork']=prior[0]['artwork']
    if prior[0].get('artwork_source'):e['artwork_source']=prior[0]['artwork_source']
    restored+=1
 return restored

def validate(old,new,old_details,new_details,audit,started,finished):
 old_time=stamp(old['updated_at']);new_time=stamp(new['updated_at'])
 if not old_time<new_time or new_time<started-dt.timedelta(minutes=5) or new_time>finished+dt.timedelta(minutes=1):raise ValueError('Refreshed timestamp is stale or outside the actual run')
 if int(new.get('source_cutoff_id',0))<int(old.get('source_cutoff_id',0)):raise ValueError('HN scan cutoff moved backwards')
 old_ids={str(x['id']) for x in old['items']};new_ids={str(x['id']) for x in new['items']}
 if len(new_ids)!=len(new['items']) or not old_ids<=new_ids:raise ValueError('A previously listed show is missing or show IDs are duplicated')
 lost=references(old)-references(new)
 if lost:raise ValueError(f'{len(lost)} existing show/comment references disappeared; manual review required')
 lost_episodes=episode_references(old_details)-episode_references(new_details)
 if lost_episodes:raise ValueError(f'{len(lost_episodes)} existing show/episode/comment references disappeared; manual review required')
 old_spotify={str(s['id']) for s in old['items'] if s.get('spotify_url')};new_spotify={str(s['id']) for s in new['items'] if s.get('spotify_url')}
 if not old_spotify<=new_spotify:raise ValueError(f'{len(old_spotify-new_spotify)} verified Spotify show links disappeared; manual review required')
 if audit.get('data_snapshot')!=new['updated_at']:raise ValueError('Episode audit and new snapshot do not match')
 return {'previous_updated_at':old['updated_at'],'updated_at':new['updated_at'],'shows':len(new_ids),'unique_comments':len({cid for _,cid in references(new)}),'episode_associations':len(episode_references(new_details)),'episodes':sum(map(len,new_details['episodes'].values())),'source_cutoff_id':new.get('source_cutoff_id')}
def copy_output(src,dst):
 dst.parent.mkdir(parents=True,exist_ok=True);tmp=dst.with_name('.'+dst.name+'.refresh-tmp');shutil.copy2(src,tmp);os.replace(tmp,dst)
def run():
 started=dt.datetime.now(dt.timezone.utc);old=read_json(ROOT/'dist/data.json');old_details=read_json(ROOT/'dist/details.json')
 with tempfile.TemporaryDirectory(prefix='hacker-podcast-refresh-') as temp:
  stage=Path(temp)
  for name in ('scripts','tests','data','dist','snapshots'):shutil.copytree(ROOT/name,stage/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
  for i,command in enumerate(STEPS,1):
   print(f'[{i}/{len(STEPS)}] {" ".join(command)}',flush=True)
   attempts=3 if command[1:]==['scripts/catalog_enrich.py'] else 1
   for attempt in range(attempts):
    try:
     subprocess.run(command,cwd=stage,check=True,timeout=900)
     break
    except (subprocess.CalledProcessError,subprocess.TimeoutExpired):
     if attempt+1==attempts:raise
     delay=20*(attempt+1)
     print(f'RSS catalogue stage failed; retrying in {delay}s ({attempt+2}/{attempts})',flush=True)
     time.sleep(delay)
  new_data=read_json(stage/'dist/data.json');new_details=read_json(stage/'dist/details.json')
  restored=preserve_episode_artwork(old_details,new_details)
  if restored:
   details_text=json.dumps(new_details,ensure_ascii=False,indent=2)
   (stage/'dist/details.json').write_text(details_text)
   (stage/'snapshots'/(new_data['updated_at'][:10]+'-details.json')).write_text(details_text)
   print(f'Restored previously verified episode artwork: {restored}',flush=True)
  result=validate(old,new_data,old_details,new_details,read_json(stage/'dist/episode-audit.json'),started,dt.datetime.now(dt.timezone.utc))
  for folder,names in OUTPUTS.items():
   for name in names:copy_output(stage/folder/name,ROOT/folder/name)
  for folder in ('data','snapshots'):
   for file in (stage/folder).glob('*.json'):copy_output(file,ROOT/folder/file.name)
  print('REFRESH_VALIDATED '+json.dumps(result,ensure_ascii=False,sort_keys=True),flush=True)
if __name__=='__main__':
 lock_path=Path(tempfile.gettempdir())/'hacker-podcast-refresh.lock'
 with lock_path.open('w') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:raise SystemExit('Another Hacker Podcast refresh is already running')
  try:run()
  except (ValueError,subprocess.CalledProcessError,subprocess.TimeoutExpired) as exc:raise SystemExit(f'Refresh failed; existing site files retained: {exc}')
