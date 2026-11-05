const fs=require('fs'),vm=require('vm'),assert=require('assert');
const script=fs.readFileSync('dist/app.js','utf8'),html=fs.readFileSync('dist/index.html','utf8');
const data=JSON.parse(fs.readFileSync('dist/data.json')), details=JSON.parse(fs.readFileSync('dist/details.json'));
async function boot(hash=''){
 const nodes={};
 function node(key){return nodes[key]??={disabled:false,hidden:false,value:'',innerHTML:'',textContent:'',dataset:{},handlers:{},classList:{classes:new Set(),toggle(k,on){if(on)this.classes.add(k);else this.classes.delete(k)},add(k){this.classes.add(k)},remove(k){this.classes.delete(k)}},addEventListener(name,fn){this.handlers[name]=fn},setAttribute(){}}}
 const nav=['browse','latest'].map(view=>{const n=node(view);n.dataset.view=view;return n});
 let href=new URL('https://test.local/'+hash);const handlers={};
 const window={get location(){return href},history:{replaceState(_a,_b,u){href=new URL(u)}},addEventListener(k,fn){handlers[k]=fn},prompt(){}};
 const context={window,document:{documentElement:{dataset:{}},querySelector:node,querySelectorAll:q=>q==='.nav button'?nav:[],getElementById:()=>({scrollIntoView(){}})},navigator:{},localStorage:{getItem:()=>null,setItem(){}},fetch:async path=>({ok:true,headers:{get:()=> 'application/json'},json:async()=>path==='/details.json'?details:data}),AbortController,URL,console,setTimeout,clearTimeout};
 vm.runInNewContext(script,context);await new Promise(resolve=>setImmediate(resolve));
 return {node,nav,go(h){href.hash=h;handlers.hashchange()},get hash(){return href.hash}};
}
const ids=a=>[...a.node('#grid').innerHTML.matchAll(/<article class="card" id="show-([^"]+)"/g)].map(m=>m[1]);
(async()=>{
 const a=await boot();assert.equal(a.node('#more').hidden,false);
 a.node('#search').value='zzzzzz-no-such-podcast';a.node('#search').handlers.input();assert.equal(ids(a).length,0);assert.equal(a.node('#more').hidden,true);
 a.node('#search').value='99% Invisible';a.node('#search').handlers.input();assert.equal(ids(a).length,1);assert.equal(a.node('#more').hidden,true);
 a.go('#show-this-american-life');assert.equal(ids(a).length,1);assert.equal(a.node('#more').hidden,true);
 a.node('#clear-share').handlers.click();a.node('#search').value='';a.node('#search').handlers.input();
 a.node('#sort').value='episode';a.node('#sort').handlers.change();const browse=ids(a);a.nav[1].handlers.click();assert.equal(a.node('#sort').value,'episode');assert.deepStrictEqual(ids(a),browse);
 assert(!html.includes('value="recently-added"'));assert(html.includes('.load[hidden]'));
 a.nav[0].handlers.click();const dailyId=a.node('#featured').innerHTML.match(/data-show-id="([^"]+)"/)[1];
 const compareNames=(x,y)=>x.title.localeCompare(y.title,'en',{sensitivity:'base'})||String(x.id).localeCompare(String(y.id),'en');
 const wanted=new Set([...data.items].sort((x,y)=>y.sources.length-x.sources.length||compareNames(x,y)).slice(0,12).map(x=>String(x.id)));wanted.add(dailyId);
 a.go('#featured-shows');assert.deepStrictEqual(new Set(ids(a)),wanted);assert.equal(a.node('#more').hidden,true);assert.equal(a.node('#back-to-all').hidden,false);assert(a.node('#featured-section').classList.classes.has('hidden'));
 assert(a.node('#status').textContent.includes("Today's pick and the most-mentioned shows"));a.node('#back-to-all').handlers.click();assert.equal(a.hash,'');assert.equal(a.node('#back-to-all').hidden,true);assert.equal(ids(a).length,20);assert.equal(a.node('#more').hidden,false);
 const b=await boot('#featured-shows');assert.deepStrictEqual(new Set(ids(b)),wanted);b.go('#show-this-american-life');assert.equal(ids(b).length,1);assert.equal(b.node('#back-to-all').hidden,true);
 assert(html.includes('.episode-info p{display:block;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}'));
 assert(/\.card\s*\{[^}]*gap:\s*12px/.test(html));
 a.node('#search').value='Short Story Collection Vol. 001';a.node('#search').handlers.input();assert.equal(ids(a).length,1);assert(!a.node('#grid').innerHTML.includes('Latest episode:'));
 a.node('#search').value='This American Life';a.node('#search').handlers.input();const rendered=a.node('#grid').innerHTML;assert(rendered.includes('class="episode-placeholder"'));assert(rendered.includes('class="episode-image"'));assert(rendered.includes('data-fallback='));
 const cls={seen:false,contains(x){return x==='episode-image'},add(x){if(x==='is-loaded')this.seen=true}};a.node('#grid').handlers.load({target:{classList:cls}});assert(cls.seen);
 const placeholder={hidden:false,classList:{contains:x=>x==='episode-placeholder'}};a.node('#grid').handlers.error({target:placeholder});assert(placeholder.hidden);
 console.log('UI simulations: Load more hidden for no/single result and deep links; Latest/Browse dates agree; curated collection and back; title CSS; artwork placeholder/load/error passed.');
 console.log('Featured count:',wanted.size,'; latest Browse/Latest first:',browse[0]);
})().catch(e=>{console.error(e);process.exit(1)});
