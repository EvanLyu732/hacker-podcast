const fs=require('fs'),vm=require('vm'),assert=require('assert');
const script=fs.readFileSync('dist/app.js','utf8');
const data=JSON.parse(fs.readFileSync('dist/data.json'));
const details=JSON.parse(fs.readFileSync('dist/details.json'));
async function boot(snapshot=data){
 const nodes={};function node(key){return nodes[key]??={disabled:false,hidden:false,value:'',innerHTML:'',textContent:'',dataset:{},handlers:{},classList:{toggle(){},add(){},remove(){}},addEventListener(name,fn){this.handlers[name]=fn},setAttribute(){}}}
 const nav=['browse','latest'].map(view=>{const n=node(view);n.dataset.view=view;return n});
 const context={document:{documentElement:{dataset:{}},querySelector:node,querySelectorAll:q=>q==='.nav button'?nav:[]},localStorage:{getItem:()=>null,setItem(){}},fetch:async path=>({ok:true,headers:{get:()=> 'application/json'},json:async()=>path==='/details.json'?details:snapshot}),AbortController,URL,console,setTimeout,clearTimeout};
 vm.runInNewContext(script,context);await new Promise(resolve=>setImmediate(resolve));return {node,nav};
}
const collator=new Intl.Collator('en',{sensitivity:'base'});
const nameOrder=(a,b)=>collator.compare(a.title,b.title)||String(a.id).localeCompare(String(b.id),'en');
const published=show=>{let value=show.latest_episode?.published;if(typeof value!=='string'||!value.trim())return null;const time=Date.parse(value);return Number.isFinite(time)?time:null};
const latestOrder=(a,b)=>{const x=published(a),y=published(b);return x===null||y===null?(x===y?nameOrder(a,b):x===null?1:-1):(y-x||nameOrder(a,b))};
const ids=app=>[...app.node('#grid').innerHTML.matchAll(/<article class="card" id="show-([^"]+)"/g)].map(m=>m[1]);
const choose=(app,mode)=>{app.node('#sort').value=mode;app.node('#sort').handlers.change()};
(async()=>{
 const app=await boot();assert.equal(app.node('#sort').value,'mentions');
 const mention=[...data.items].sort((a,b)=>b.sources.length-a.sources.length||nameOrder(a,b));
 assert.deepStrictEqual(ids(app),mention.slice(0,20).map(x=>String(x.id)));
 app.node('#more').handlers.click();assert.equal(ids(app).length,40);
 choose(app,'episode');const latest=[...data.items].sort(latestOrder);assert.equal(ids(app).length,40);assert.deepStrictEqual(ids(app),latest.slice(0,40).map(x=>String(x.id)));
 while(!app.node('#more').hidden)app.node('#more').handlers.click();assert.equal(ids(app).length,data.items.length);assert.deepStrictEqual(ids(app),latest.map(x=>String(x.id)));
 const undated=latest.filter(s=>published(s)===null);if(undated.length)assert(latest.slice(-undated.length).every(s=>published(s)===null));
 choose(app,'name');const alphabetic=[...data.items].sort(nameOrder);assert.equal(ids(app).length,data.items.length);assert.deepStrictEqual(ids(app),alphabetic.map(x=>String(x.id)));assert.notDeepStrictEqual(alphabetic.map(x=>x.id),latest.map(x=>x.id));
 choose(app,'mentions');assert.equal(ids(app).length,data.items.length);assert.deepStrictEqual(ids(app),mention.map(x=>String(x.id)));assert.notDeepStrictEqual(mention.map(x=>x.id),alphabetic.map(x=>x.id));assert.notDeepStrictEqual(mention.map(x=>x.id),latest.map(x=>x.id));
 app.node('#search').value='Planet Money';app.node('#search').handlers.input();choose(app,'name');assert.equal(app.node('#search').value,'Planet Money');assert(app.node('#grid').innerHTML.includes('>Planet Money</h3>'));
 app.node('#search').value='';app.node('#search').handlers.input();app.nav[1].handlers.click();assert.equal(app.node('#sort').value,'episode');assert.deepStrictEqual(ids(app),latest.slice(0,20).map(x=>String(x.id)));
 const fixture={...data,items:[
  {...data.items[0],id:'1',title:'Zulu',latest_episode:{published:'not a date'}},
  {...data.items[1],id:'2',title:'Alpha',latest_episode:{published:'2024-01-01T00:00:00Z'}},
  {...data.items[2],id:'3',title:'Beta',latest_episode:null},
  {...data.items[3],id:'4',title:'Delta',latest_episode:{published:'2025-01-01T00:00:00Z'}},
 ]};const synthetic=await boot(fixture);choose(synthetic,'episode');assert.deepStrictEqual(ids(synthetic),['4','2','3','1']);
 console.log('Sort: mention count, episode date (missing/invalid last), English name order, pagination and search passed (DOM simulation)');
 console.log('Top 3 mentions:',mention.slice(0,3).map(x=>x.title).join(' | '));
 console.log('Top 3 latest episode:',latest.slice(0,3).map(x=>x.title).join(' | '));
 console.log('Top 3 name:',alphabetic.slice(0,3).map(x=>x.title).join(' | '));
})().catch(error=>{console.error(error);process.exit(1)});
