const fs=require('fs'),vm=require('vm'),assert=require('assert');
const script=fs.readFileSync('dist/app.js','utf8');
const data=JSON.parse(fs.readFileSync('dist/data.json'));
const details=JSON.parse(fs.readFileSync('dist/details.json'));
const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function boot(detailsUnavailable=false,snapshot=data,episodeSnapshot=details){
 const nodes={};function node(key){return nodes[key]??={disabled:false,hidden:false,value:'',innerHTML:'',textContent:'',dataset:{},handlers:{},classList:{toggle(){},add(){},remove(){}},addEventListener(name,fn){this.handlers[name]=fn},setAttribute(){}}}
 const nav=['browse','latest'].map(view=>{const n=node(view);n.dataset.view=view;return n});
 const context={document:{documentElement:{dataset:{}},querySelector:node,querySelectorAll:q=>q==='.nav button'?nav:[]},localStorage:{getItem:()=>null,setItem(){}},fetch:async path=>path==='/details.json'&&detailsUnavailable?{ok:false,status:503}:{ok:true,headers:{get:()=> 'application/json'},json:async()=>path==='/details.json'?episodeSnapshot:snapshot},AbortController,URL,console,setTimeout,clearTimeout};
 vm.runInNewContext(script,context);await new Promise(resolve=>setImmediate(resolve));return {node,nav};
}
function search(app,query){app.node('#search').value=query;app.node('#search').handlers.input();return app.node('#grid').innerHTML;}
(async()=>{
 const app=await boot();const initial=app.node('#grid').innerHTML;
 const ranked=[...data.items].sort((a,b)=>b.sources.length-a.sources.length||a.title.localeCompare(b.title));
 const show=ranked.find((x,i)=>i>=20&&x.title==='Planet Money');assert(show);assert(!initial.includes(`id="show-${show.id}"`));
 let html=search(app,show.title);assert(html.includes(`id="show-${show.id}"`));
 const episode="What to do when you're in a class action";assert((details.episodes[show.id]||[]).some(e=>e.title===episode));
 html=search(app,episode);assert(html.includes(`id="show-${show.id}"`));assert(html.includes('Matching episode: '+escape(episode)));assert(html.includes('<details class="episode-box episode-list">'));assert(html.includes('<details class="episode-disclosure">'));
 const latestShow=data.items.find(x=>x.title==='Search Engine');const latest=latestShow.latest_episode.title;
 html=search(app,latest);assert(html.includes(`id="show-${latestShow.id}"`));assert(html.includes('Latest episode: '+escape(latest)));
 const latest99=data.items.find(x=>x.title==='99% Invisible');if(latest99.latest_episode?.title){html=search(app,latest99.latest_episode.title);assert(html.includes(`id="show-${latest99.id}"`));assert(html.includes('Latest episode: '+escape(latest99.latest_episode.title)));}
 html=search(app,'zzzz-no-such-show-93475');assert(html.includes('No shows found.'));
 const comment=details.comments['3724249'].text.slice(0,35);html=search(app,comment);assert(!html.includes('>EconTalk</h3>'));
 app.nav[1].handlers.click();html=search(app,episode);assert(html.includes(`id="show-${show.id}"`));
 const partial=await boot(true);assert(partial.node('#status').textContent.includes('Mentioned episode search unavailable'));assert(search(partial,show.title).includes(`id="show-${show.id}"`));assert(search(partial,latest).includes(`id="show-${latestShow.id}"`));
 const n=data.items.find(x=>x.title==='99% Invisible');html=search(app,n.title);assert(html.includes(`id="show-${n.id}"`));assert((html.match(/class="episode-search-match"/g)||[]).length<=5);assert(html.indexOf('class="show-info"')<html.indexOf('class="card-details"'));
 const fixture=JSON.parse(JSON.stringify(data)),fixtureDetails=JSON.parse(JSON.stringify(details));const nf=fixture.items.find(x=>x.id===n.id);nf.latest_episode={title:'630: Sinners On The Rise',published:'2026-11-01T00:00:00Z'};const sid=String(nf.sources[0].id);fixtureDetails.episodes[n.id].push({title:'Somewhere Out There - 99% Invisible',url:'https://example.com/episode/somewhere',source_id:sid,source_ids:[sid]});
 for(let i=1;i<=20;i++)fixtureDetails.episodes[n.id].push({title:`Satellite Segment ${i} - 99% Invisible`,url:`https://example.com/episode/satellite-${i}`,source_id:sid,source_ids:[sid]});
 const staged=await boot(false,fixture,fixtureDetails);for(const q of ['Sinners','630']){html=search(staged,q);assert(html.includes(`id="show-${n.id}"`));assert(html.includes('Latest episode: 630: Sinners On The Rise'));}
 html=search(staged,'Somewhere Out There');assert(html.includes(`id="show-${n.id}"`));assert(html.includes('Matching episode: Somewhere Out There'));
 html=search(staged,'Satellite Segment');const panel=html.split('<div class="episode-match-panel">')[1].split('<details class="episode-box episode-list">')[0];const sections=panel.split('<details class="episode-match-more">');assert.equal(sections.length,2);assert.equal((sections[0].match(/class="episode-search-match"/g)||[]).length,5);assert(sections[1].includes('<summary>+15 more</summary>'));assert.equal((sections[1].match(/class="episode-search-match"/g)||[]).length,15);
 html=search(staged,n.title);assert(html.includes('Latest episode: 630: Sinners On The Rise'));assert((html.match(/class="episode-search-match"/g)||[]).length<=5);assert(html.indexOf('class="show-info"')<html.indexOf('Latest episode:'));assert(html.indexOf('Latest episode:')<html.indexOf('class="card-actions"'));assert(html.indexOf('class="card-actions"')<html.indexOf('class="card-details"'));
 console.log('Search: all shows, mentioned/latest episode titles, no results, no comment matching and partial-data warning passed (DOM simulation)');
})().catch(error=>{console.error(error);process.exit(1)});
