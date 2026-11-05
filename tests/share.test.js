const fs=require('fs'),vm=require('vm'),assert=require('assert');
const script=fs.readFileSync('dist/app.js','utf8');
const data=JSON.parse(fs.readFileSync('dist/data.json'));
const details=JSON.parse(fs.readFileSync('dist/details.json'));
const origin='https://hacker-podcast-archive.fluffylynx1025.chatgpt.site/';

async function boot(hash='',clipboard=true,snapshot=data){
 const nodes={},handlers={},copied=[],scrolled=[],prompts=[];
 function node(key){return nodes[key]??={disabled:false,hidden:false,value:'',innerHTML:'',textContent:'',dataset:{},handlers:{},classList:{toggle(){},add(){},remove(){}},addEventListener(name,fn){this.handlers[name]=fn},setAttribute(){}};}
 const nav=['browse','latest'].map(view=>{const n=node(view);n.dataset.view=view;return n});
 let current=new URL(origin+hash);
 const location={get href(){return current.href},get hash(){return current.hash}};
 const window={location,history:{replaceState(_state,_title,href){current=new URL(href)}},addEventListener(type,fn){handlers[type]=fn},prompt(message,link){prompts.push({message,link})}};
 const document={documentElement:{dataset:{}},querySelector:node,querySelectorAll:q=>q==='.nav button'?nav:[],getElementById:id=>node('#grid').innerHTML.includes(`id="${id}"`)?{scrollIntoView:()=>scrolled.push(id)}:null};
 const navigator={clipboard:clipboard?{writeText:async text=>copied.push(text)}:undefined};
 const context={window,document,navigator,localStorage:{getItem:()=>null,setItem(){}},fetch:async path=>({ok:true,headers:{get:()=> 'application/json'},json:async()=>path==='/details.json'?details:snapshot}),AbortController,URL,console,setTimeout,clearTimeout};
 vm.runInNewContext(script,context);await new Promise(resolve=>setImmediate(resolve));
 return {nodes,node,nav,copied,scrolled,prompts,window,go(hash){current=new URL(origin+hash);handlers.hashchange()}};
}
(async()=>{
 const app=await boot();
 assert(!app.node('#grid').innerHTML.includes('data-share-id='));assert(!app.node('#grid').innerHTML.includes('↗ Share'));
 const featured=app.node('#featured').innerHTML;assert(!featured.includes('data-share-id='));assert(!featured.includes('feature-share'));assert(!featured.includes('↗ Share'));
 const chosen=data.items.find(x=>String(x.id)===featured.match(/data-show-id="([^"]+)"/)[1]);assert(chosen);const expected=chosen.spotify_url||chosen.url;assert(featured.includes(`href="${expected.replace(/&/g,'&amp;')}"`));assert(featured.includes('<span aria-hidden="true">↗</span>'));
 const noSpotify={...data,items:data.items.map(x=>x.id===chosen.id?{...x,spotify_url:''}:x)};const fallback=await boot('',true,noSpotify);assert(fallback.node('#featured').innerHTML.includes(`href="${chosen.url.replace(/&/g,'&amp;')}"`));assert(fallback.node('#featured').innerHTML.includes('<span aria-hidden="true">↗</span>'));
 app.nav[1].handlers.click();assert(!app.node('#grid').innerHTML.includes('data-share-id='));assert(!app.node('#grid').innerHTML.includes('↗ Share'));
 app.node('#search').value='Lex Fridman';app.node('#search').handlers.input();assert(app.node('#grid').innerHTML.includes('Lex Fridman Podcast'));assert(!app.node('#grid').innerHTML.includes('data-share-id='));
 app.go('#featured-shows');assert(!app.node('#grid').innerHTML.includes('data-share-id='));assert(!app.node('#grid').innerHTML.includes('↗ Share'));
 const samples=[data.items[0],data.items[30],data.items.at(-1)];
 for(const show of samples){
  const tab=await boot('#show-'+show.id);const html=tab.node('#grid').innerHTML;
  assert.equal((html.match(/<article class="card"/g)||[]).length,1);
  assert(html.includes(`id="show-${show.id}" data-shared="true"`));assert(html.includes('>'+show.title+'</h3>'));
  assert.deepStrictEqual(tab.scrolled,['show-'+show.id]);assert(!tab.node('#clear-share').hidden);
  tab.node('#clear-share').handlers.click();assert.equal((tab.node('#grid').innerHTML.match(/<article class="card"/g)||[]).length,20);assert.equal(tab.window.location.hash,'');
 }
 app.go('#show-'+samples[2].id);assert(app.node('#grid').innerHTML.includes(`id="show-${samples[2].id}"`));assert.equal(app.node('#search').value,'');
 app.nav[0].handlers.click();assert.equal(app.window.location.hash,'');assert.equal((app.node('#grid').innerHTML.match(/<article class="card"/g)||[]).length,20);
 const missing=await boot('#show-999999999999');assert(missing.node('#grid').innerHTML.includes('This shared show is not available.'));assert(!missing.node('#clear-share').hidden);
 const tal=data.items.find(show=>show.title==='This American Life');assert(tal);
 for(const hash of ['#show-this-american-life','#show-thisamericanlife','#show-41zWZdWCpVQrKj7ykQnXRc']){const tab=await boot(hash);assert.equal((tab.node('#grid').innerHTML.match(/<article class="card"/g)||[]).length,1);assert(tab.node('#grid').innerHTML.includes(`id="show-${tal.id}"`));assert.deepStrictEqual(tab.scrolled,['show-'+tal.id]);tab.node('#clear-share').handlers.click();assert.equal(tab.window.location.hash,'');}
 for(const hash of ['#show-no-such-podcast','#show-','#show-%E0%A4%A']){const tab=await boot(hash);assert(tab.node('#grid').innerHTML.includes('This shared show is not available.'));assert(!tab.node('#clear-share').hidden);assert.equal((tab.node('#grid').innerHTML.match(/<article class="card"/g)||[]).length,0);}
 const dupe={...data,items:[...data.items,{...tal,id:'999999999999',spotify_url:''}]};const ambiguous=await boot('#show-this-american-life',true,dupe);assert(ambiguous.node('#grid').innerHTML.includes('This shared show is not available.'));
 console.log('Share buttons absent from Browse/Latest/Featured/search; existing deep links, hash changes and return to all shows passed (DOM simulation)');
})().catch(error=>{console.error(error);process.exit(1)});
