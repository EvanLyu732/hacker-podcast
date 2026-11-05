'use strict';
(() => {
  const $ = s => document.querySelector(s), grid=$('#grid'), search=$('#search'), more=$('#more'), sort=$('#sort'), status=$('#status');
  const controls = [...document.querySelectorAll('.nav button'), search, sort];
  let all=[], dailyPool=[], dailyTimer=null, snapshotTime='', filterView='browse', limit=20, sortMode='mentions', generation=0, sharedId=null, episodeDetailsAvailable=false, details={comments:{},episodes:{}};
  sort.value=sortMode;
  let theme='light';try{if(localStorage.getItem('hp-theme')==='dark')theme='dark';}catch(_){}
  const themeButton=$('#theme-toggle');
  function applyTheme(){document.documentElement.dataset.theme=theme;themeButton.textContent=theme==='dark'?'☀ Light':'☾ Dark';themeButton.setAttribute('aria-label',theme==='dark'?'Switch to light theme':'Switch to dark theme');}
  themeButton.addEventListener('click',()=>{theme=theme==='dark'?'light':'dark';try{localStorage.setItem('hp-theme',theme)}catch(_){}applyTheme()});applyTheme();
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function url(s) { try { const u=new URL(s); return ['http:','https:'].includes(u.protocol)?u.href:''; } catch (_) { return ''; } }
  function imageUrl(s) { try {const u=new URL(s);return u.protocol==='https:'&&!u.username&&!u.password?u.href:'';}catch(_){return '';} }
  function artworkReferrerPolicy(s){try{const host=new URL(s).hostname.toLowerCase();return (host==='thisamericanlife.org'||host.endsWith('.thisamericanlife.org'))?' referrerpolicy="no-referrer"':'';}catch(_){return '';}}
  function controlsEnabled(on){controls.forEach(x=>x.disabled=!on);}
  function spotify(x){const link=url(x.spotify_url);return /^https:\/\/open\.spotify\.com\/show\/[a-zA-Z0-9]+\/?$/.test(link)?link:'';}
  function cover(x){const img=url(x.artwork);return img?`<img class="cover" loading="lazy" src="${esc(img)}" alt="${esc(x.title)} cover">`:`<div class="cover-placeholder" aria-label="No cover available">♪</div>`;}
  // Hash show IDs only to give the stable pool a varied, device-independent order.
  function stableIdHash(value){let h=2166136261;for(const c of String(value)){h^=c.charCodeAt(0);h=Math.imul(h,16777619);}return h>>>0;}
  function buildDailyPool(shows){return shows.map(show=>({show,hash:stableIdHash(show.id)})).sort((a,b)=>a.hash-b.hash||(String(a.show.id)<String(b.show.id)?-1:String(a.show.id)>String(b.show.id)?1:0)).map(entry=>entry.show);}
  function dailyShow(now=new Date()){if(!dailyPool.length)return null;const day=Math.floor(Date.UTC(now.getFullYear(),now.getMonth(),now.getDate())/86400000);return dailyPool[((day%dailyPool.length)+dailyPool.length)%dailyPool.length];}
  function renderFeatured(){const x=dailyShow();if(!x)return;$('#featured').innerHTML=`<div class="feature" data-show-id="${esc(x.id)}"><div class="feature-label">FEATURED DISCOVERY</div><h3>${esc(x.title)}</h3><p>${esc(x.artist)}</p><a href="${esc(spotify(x)||url(x.url))}" target="_blank" rel="noopener" aria-label="Open ${esc(x.title)}"><div class="feature-art${url(x.artwork)?'':' no-image'}">${url(x.artwork)?`<img src="${esc(url(x.artwork))}" alt="">`:''}<strong>${esc(x.title)}</strong><span aria-hidden="true">↗</span></div></a></div>`;}
  function scheduleDailyRefresh(){if(dailyTimer!==null)clearTimeout(dailyTimer);const now=new Date(),next=new Date(now.getFullYear(),now.getMonth(),now.getDate()+1);dailyTimer=setTimeout(()=>{if(filterView==='featured')render();else renderFeatured();scheduleDailyRefresh();},Math.max(1000,next.getTime()-now.getTime()+100));if(typeof dailyTimer?.unref==='function')dailyTimer.unref();}
  function sourcePanel(x,q) {
    const orderedSources=[...x.sources].sort((a,b)=>{const aTime=Date.parse(a.date||''),bTime=Date.parse(b.date||'');return (Number.isFinite(bTime)?bTime:-Infinity)-(Number.isFinite(aTime)?aTime:-Infinity)||String(a.id).localeCompare(String(b.id));});
    const sourceIds=new Set(orderedSources.map(s=>String(s.id)));
    function ids(e){return [...new Set((Array.isArray(e.source_ids)?e.source_ids:[e.source_id]).map(String))].filter(id=>sourceIds.has(id));}
    const episodes=(details.episodes?.[x.id]||[]).filter(e=>ids(e).length&&url(e.url));
    const linkedIds=new Set(episodes.flatMap(ids));
    function comment(s){
      const full=details.comments?.[String(s.id)],text=full?.text||s.text||'Comment unavailable',rawDate=String(s.date||'');
      const stamp=Date.parse(rawDate),hasTime=/T\d{2}:\d{2}/.test(rawDate)&&Number.isFinite(stamp);
      const when=hasTime?new Date(stamp).toISOString().slice(0,16).replace('T',' ')+' UTC':rawDate.slice(0,10);
      const excerpt=hasTime?'':`<span class="comment-excerpt">${esc(text.replace(/\s+/g,' ').trim().slice(0,90))}</span>`;
      return `<details class="comment" data-source-id="${esc(s.id)}"><summary>${esc(s.author||'HN user')} <span>${esc(when)}</span>${excerpt}</summary><p class="comment-text" tabindex="0">${esc(text)}</p>${!full?.full?'<small>Only an excerpt is available.</small>':''}<a class="source-original" href="https://news.ycombinator.com/item?id=${encodeURIComponent(s.id)}" target="_blank" rel="noopener">View original on HN ↗</a></details>`;
    }
    const episodeBlock=episodes.length?episodes.map(e=>{const art=imageUrl(e.artwork),fallback=imageUrl(x.artwork);const primary=art||fallback;const fallbackAttr=art&&fallback&&art!==fallback?` data-fallback="${esc(fallback)}"`:'';const placeholder=art&&fallback&&art!==fallback?`<img class="episode-placeholder" src="${esc(fallback)}" alt="" aria-hidden="true" loading="lazy">`:'';const related=new Set(ids(e));const comments=orderedSources.filter(s=>related.has(String(s.id)));return `<li class="episode-item" data-episode-url="${esc(url(e.url))}"><details class="episode-disclosure"><summary class="episode-toggle">${esc(episodeSearchTitle(e.title,x.title))}</summary><div class="episode-content"><div class="episode-heading"><span class="episode-artwork">${primary?`${placeholder}<img class="episode-image" src="${esc(primary)}"${fallbackAttr}${artworkReferrerPolicy(primary)} alt="${esc(art?episodeSearchTitle(e.title,x.title)+' episode artwork':x.title+' show artwork')}" loading="lazy"><span class="no-artwork" hidden>No image</span>`:'<span class="no-artwork">No image</span>'}</span><a href="${esc(url(e.url))}" target="_blank" rel="noopener">Open episode ↗</a></div><div class="episode-comments"><span class="comment-label">HN comments</span>${comments.map(comment).join('')}</div></div></details></li>`}).join(''):'';
    const general=orderedSources.filter(s=>!linkedIds.has(String(s.id)));
    const matches=matchedEpisodes(x,q).filter(title=>title!==x.latest_episode?.title);
    const matchLine=title=>`<p class="episode-search-match">Matching episode: ${esc(episodeSearchTitle(title,x.title))}</p>`;
    const matchPanel=matches.length?`<div class="episode-match-panel">${matches.slice(0,5).map(matchLine).join('')}${matches.length>5?`<details class="episode-match-more"><summary>+${matches.length-5} more</summary>${matches.slice(5).map(matchLine).join('')}</details>`:''}</div>`:'';
    return `<div class="card-details">${matchPanel}${episodes.length?`<details class="episode-box episode-list"><summary class="episode-list-toggle">Mentioned episodes</summary><ul>${episodeBlock}</ul></details>`:`<p class="empty-detail">${episodeDetailsAvailable?'No mentioned episodes':'Episode details unavailable'}</p>`}${general.length?`<details class="source-list"><summary>Show comments</summary>${general.map(comment).join('')}</details>`:'<p class="empty-detail">No comments</p>'}</div>`;
  }
  function episodeSearchTitle(title,showTitle){
    let text=String(title||'').trimEnd();const name=String(showTitle||'');
    const suffixes=[name,...(name.toLowerCase()==='econtalk'?['Econlib']:[])];
    for(const suffix of suffixes){if(!suffix||!text.toLowerCase().endsWith(suffix.toLowerCase()))continue;const prefix=text.slice(0,-suffix.length);if(/\s+[-–—|]\s*$/.test(prefix)){text=prefix.replace(/\s+[-–—|]\s*$/,'');break;}}
    if(name.toLowerCase()==='99% invisible'&&/^Mini-Stories: Volume 8 - Page 2 of 4$/i.test(text))return 'Mini-Stories: Volume 8';
    return text;
  }
  function matchedEpisodes(show,q){
    if(!q)return [];
    const titles=[show.latest_episode?.title,...(details.episodes?.[show.id]||[]).map(e=>e.title)];
    const showName=String(show.title||'').toLowerCase();
    return [...new Set(titles.filter(title=>typeof title==='string'&&(episodeSearchTitle(title,show.title).toLowerCase().includes(q)||(showName&&q!==showName&&q.includes(showName)&&title.toLowerCase().includes(q)))))];
  }
  function compareNames(a,b){return a.title.localeCompare(b.title,'en',{sensitivity:'base'})||String(a.id).localeCompare(String(b.id),'en');}
  function episodeDate(show){const value=show.latest_episode?.published;if(typeof value!=='string'||!value.trim())return null;const date=Date.parse(value);return Number.isFinite(date)?date:null;}
  function compareShows(a,b){
    if(sortMode==='name')return compareNames(a,b);
    if(sortMode==='episode'){
      const aDate=episodeDate(a),bDate=episodeDate(b);
      if(aDate===null||bDate===null)return aDate===bDate?compareNames(a,b):(aDate===null?1:-1);
      return bDate-aDate||compareNames(a,b);
    }
    return b.sources.length-a.sources.length||compareNames(a,b);
  }
  function featuredIds(){const selected=new Set([...all].sort((a,b)=>b.sources.length-a.sources.length||compareNames(a,b)).slice(0,12).map(show=>String(show.id)));const daily=dailyShow();if(daily)selected.add(String(daily.id));return selected;}
  function render() {
    const q=search.value.trim().toLowerCase();
    const featuredSelection=filterView==='featured'?featuredIds():null;
    let items=all.filter(x=>(sharedId===null||String(x.id)===sharedId)&&(!featuredSelection||featuredSelection.has(String(x.id)))&&(!q||[x.title,x.artist,...(x.genres||[])].join(' ').toLowerCase().includes(q)||matchedEpisodes(x,q).length));
    items.sort(compareShows);
    const featured=filterView==='browse'&&!q&&sharedId===null&&all.length>0;
    $('#featured-section').classList.toggle('hidden',!featured);
    if(featured) renderFeatured();
    $('#updated').textContent=`${items.length} ${items.length===1?'show':'shows'}${q?' found':''} · Updated ${snapshotTime}`;
    status.textContent=`${items.length} ${items.length===1?'show':'shows'}${q?' found':''} · ${filterView==='featured'?"Today's pick and the most-mentioned shows":'From Hacker News comments'}${episodeDetailsAvailable?'':' · Mentioned episode search unavailable'}`;
    $('#clear-share').hidden=sharedId===null;
    $('#back-to-all').hidden=filterView!=='featured';
    grid.innerHTML=items.slice(0,limit).map((x,i)=>`<article class="card" id="show-${esc(x.id)}"${sharedId!==null?' data-shared="true"':''}><span class="card-number">${q?'':i+1}</span><a class="show-info" href="${esc(spotify(x)||url(x.url))}" target="_blank" rel="noopener" aria-label="Open ${esc(x.title)}">${cover(x)}<div class="show-copy"><h3>${esc(x.title)}</h3><p>${esc(x.artist)}</p></div></a>${x.latest_episode?.title&&episodeDate(x)!==null?`<div class="episode-info"><p>Latest episode: ${esc(episodeSearchTitle(x.latest_episode.title,x.title))}</p></div>`:''}<div class="card-actions">${spotify(x)?`<a class="spotify-link" href="${esc(spotify(x))}" target="_blank" rel="noopener" aria-label="Open on Spotify: ${esc(x.title)}">◉ Spotify ↗</a>`:''}<a href="${esc(url(x.url))}" target="_blank" rel="noopener" aria-label="Open in Apple Podcasts: ${esc(x.title)}">Apple ↗</a>${url(x.feed_url)?`<a href="${esc(url(x.feed_url))}" target="_blank" rel="noopener">RSS ↗</a>`:''}</div>${sourcePanel(x,q)}</article>`).join('')||(sharedId!==null?'<div class="empty">This shared show is not available.</div>':'<div class="empty">No shows found. Try another search or return to Browse.</div>');
    more.hidden=items.length<=limit;
  }
  function clearShared(){
    if(sharedId===null)return;
    sharedId=null;
    if(typeof window!=='undefined'&&/^#show-/i.test(window.location.hash)){
      const clean=new URL(window.location.href);clean.hash='';window.history.replaceState(null,'',clean.href);
    }
  }
  function showSlug(value){return String(value||'').normalize('NFKD').replace(/\p{M}/gu,'').toLowerCase().replace(/[^\p{L}\p{N}]+/gu,'-').replace(/^-+|-+$/g,'');}
  function sharedShow(identifier){
    const ids=all.filter(show=>{
      if(String(show.id)===identifier)return true;
      const link=spotify(show);return link&&new URL(link).pathname.split('/')[2]===identifier;
    });
    if(ids.length)return ids.length===1?ids[0]:null;
    const slug=showSlug(identifier);if(!slug)return null;
    const exact=all.filter(show=>showSlug(show.title)===slug);
    if(exact.length)return exact.length===1?exact[0]:null;
    const compact=slug.replace(/-/g,'');const matches=all.filter(show=>showSlug(show.title).replace(/-/g,'')===compact);
    return matches.length===1?matches[0]:null;
  }
  function openShared(){
    if(typeof window==='undefined'||!all.length)return false;
    const match=/^#show-(.*)$/i.exec(window.location.hash);
    if(!match)return false;
    let identifier='';try{identifier=decodeURIComponent(match[1]);}catch(_){}
    const show=sharedShow(identifier);if(filterView==='featured'){filterView='browse';$('#page-title').textContent='Browse';$('#collection-title').textContent='Community picks';document.querySelectorAll('.nav button').forEach(x=>{x.classList.remove('active');if(x.dataset.view==='browse')x.classList.add('active')});}sharedId=show?String(show.id):'unavailable';search.value='';limit=20;render();
    if(show)document.getElementById('show-'+sharedId)?.scrollIntoView({block:'center'});
    return true;
  }
  function openFeatured(){
    if(typeof window==='undefined'||!all.length||window.location.hash.toLowerCase()!=='#featured-shows')return false;
    sharedId=null;filterView='featured';search.value='';limit=20;sortMode='mentions';sort.value=sortMode;
    document.querySelectorAll('.nav button').forEach(x=>x.classList.remove('active'));
    $('#page-title').textContent='Featured';$('#collection-title').textContent='Featured shows';render();return true;
  }
  function setView(view){
    clearShared();
    if(typeof window!=='undefined'&&window.location.hash.toLowerCase()==='#featured-shows'){const clean=new URL(window.location.href);clean.hash='';window.history.replaceState(null,'',clean.href);}
    document.querySelectorAll('.nav button').forEach(x=>{x.classList.remove('active');if(x.dataset.view===view)x.classList.add('active')});
    filterView=view;$('#page-title').textContent={browse:'Browse',latest:'Latest'}[view];$('#collection-title').textContent=view==='latest'?'Latest episodes':'Community picks';sortMode=view==='latest'?'episode':'mentions';sort.value=sortMode;limit=20;render();
  }
  async function load(){
    const current=++generation;controlsEnabled(false);more.hidden=true;$('#featured-section').classList.add('hidden');status.textContent='Loading podcast data…';grid.innerHTML='<div class="skeleton"></div>'.repeat(5);
    const controller=new AbortController(), timer=setTimeout(()=>controller.abort(),8000);
    try {
      const response=await fetch('/data.json',{signal:controller.signal,cache:'no-cache'});
      if(!response.ok)throw Error(`HTTP ${response.status}`);
      if(!(response.headers.get('content-type')||'').includes('json'))throw Error('The data endpoint did not return JSON');
      const data=await response.json();if(current!==generation)return;
      if(!Array.isArray(data.items)||!data.version||!data.updated_at)throw Error('Invalid data format');
      all=data.items.filter(x=>x.id&&x.title&&url(x.url)&&Array.isArray(x.sources));
      if(!all.length)throw Error('No shows are available in this snapshot');
      dailyPool=buildDailyPool(all);
      episodeDetailsAvailable=false;
      try { const extra=await fetch('/details.json',{signal:controller.signal,cache:'no-cache'}); if(!extra.ok||!(extra.headers.get('content-type')||'').includes('json'))throw Error('Episode details unavailable');const parsed=await extra.json();if(!parsed.episodes||typeof parsed.episodes!=='object')throw Error('Invalid episode details');details={comments:parsed.comments||{},episodes:parsed.episodes};episodeDetailsAvailable=true; } catch (_) { details={comments:{},episodes:{}}; }
      if(current!==generation)return;
      controlsEnabled(true);snapshotTime=new Date(data.updated_at).toLocaleString('en-US',{timeZone:'Asia/Shanghai'});
      if(!openShared()&&!openFeatured())render();scheduleDailyRefresh();
    } catch(e) {if(current!==generation)return;controlsEnabled(false);status.textContent='Data unavailable. Search and navigation are disabled.';grid.innerHTML=`<div class="error">Unable to load data: ${esc(e.name==='AbortError'?'Request timed out after 8 seconds':e.message)}<button id="retry">Try again</button></div>`;$('#retry').addEventListener('click',load);} finally{clearTimeout(timer);}
  }
  document.querySelectorAll('.nav button').forEach(b=>b.addEventListener('click',()=>setView(b.dataset.view)));
  search.addEventListener('input',()=>{clearShared();limit=20;render()});sort.addEventListener('change',()=>{if(!['mentions','episode','name'].includes(sort.value))return;sortMode=sort.value;render()});more.addEventListener('click',()=>{limit+=20;render()});
  $('#clear-share').addEventListener('click',()=>{clearShared();render()});
  $('#back-to-all').addEventListener('click',()=>setView('browse'));
  if(typeof window!=='undefined')window.addEventListener('hashchange',()=>{if(openShared()||openFeatured())return;if(filterView==='featured'){setView('browse');return}if(sharedId!==null){sharedId=null;render();}});
  // Capture image errors from dynamically rendered episode artwork, retrying the show cover once.
  grid.addEventListener('load',event=>{const img=event.target;if(img.classList?.contains('episode-image'))img.classList.add('is-loaded');},true);
  grid.addEventListener('error',event=>{const img=event.target;if(img.classList?.contains('episode-placeholder')){img.hidden=true;return}if(!img.matches?.('.episode-artwork img'))return;const fallback=img.dataset.fallback;if(fallback&&img.src!==fallback){delete img.dataset.fallback;img.alt='Show artwork';img.src=fallback;return;}img.hidden=true;const label=img.nextElementSibling;if(label)label.hidden=false;},true);
  load();
})();
