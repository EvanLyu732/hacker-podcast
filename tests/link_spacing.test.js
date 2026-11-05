const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('dist/index.html','utf8'),script=fs.readFileSync('dist/app.js','utf8');
const data=JSON.parse(fs.readFileSync('dist/data.json')),details=JSON.parse(fs.readFileSync('dist/details.json'));
async function boot(){
 const nodes={};function node(k){return nodes[k]??={disabled:false,hidden:false,value:'',innerHTML:'',textContent:'',dataset:{},handlers:{},classList:{toggle(){},add(){},remove(){}},addEventListener(n,f){this.handlers[n]=f},setAttribute(){}}}
 const nav=['browse','latest'].map(view=>{const n=node(view);n.dataset.view=view;return n});
 const context={document:{documentElement:{dataset:{}},querySelector:node,querySelectorAll:q=>q==='.nav button'?nav:[]},localStorage:{getItem:()=>null,setItem(){}},fetch:async path=>({ok:true,headers:{get:()=> 'application/json'},json:async()=>path==='/details.json'?details:data}),AbortController,URL,console,setTimeout,clearTimeout};
 vm.runInNewContext(script,context);await new Promise(resolve=>setImmediate(resolve));return {node,nav};
}
(async()=>{
 assert(html.includes('@media(min-width:1001px){.list-head,.card{grid-template-columns:28px minmax(210px,1.2fr) minmax(0,1fr) 280px;column-gap:20px}}'));
 assert(html.includes('@media(min-width:601px){.card-actions{justify-content:flex-start}}'));
 assert(html.includes('.episode-info p{display:block;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}'));
 assert(html.includes('<footer class="version">Hacker Podcast · v3.0.6</footer>'));
 assert(html.includes('/app.js?v=3.0.6'));
 const app=await boot();
 for(const view of ['browse','latest']){
  app.nav.find(x=>x.dataset.view===view).handlers.click();app.node('#sort').value='episode';app.node('#sort').handlers.change();
  for(const [query,title] of [['Empire','410. JFK: Blood On The Streets Of Dallas (Part 4)'],['The Talk Show With John Gruber','456:'],['Señors at Scale','The unwritten rules of engineering management']]){
   app.node('#search').value=query;app.node('#search').handlers.input();const out=app.node('#grid').innerHTML;
   assert(out.includes(title));assert(out.includes('class="spotify-link"'));assert(out.indexOf('class="episode-info"')<out.indexOf('class="card-actions"'));
  }
  app.node('#search').value='';app.node('#search').handlers.input();
 }
 console.log('Browse/Latest: three reported titles render before their Spotify link; desktop grid uses a 280px link column and 20px gap; footer version present (DOM/CSS inspection, not a visual browser test).');
})().catch(e=>{console.error(e);process.exit(1)});
