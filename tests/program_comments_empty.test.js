const fs=require('fs'),vm=require('vm'),assert=require('assert');
const script=fs.readFileSync('dist/app.js','utf8'),data=JSON.parse(fs.readFileSync('dist/data.json')),details=JSON.parse(fs.readFileSync('dist/details.json'));
const examples=['1056200096','1373812661','1380008439','1548604447','1042433083','1827500070'];
async function boot(hash=''){
 const nodes={};function node(k){return nodes[k]??={disabled:false,hidden:false,value:'',innerHTML:'',textContent:'',dataset:{},handlers:{},classList:{toggle(){},add(){},remove(){}},addEventListener(n,f){this.handlers[n]=f},setAttribute(){}}}
 const nav=['browse','latest'].map(v=>{const n=node(v);n.dataset.view=v;return n});let href=new URL('https://test.local/'+hash);const handlers={};
 const window={get location(){return href},history:{replaceState(_a,_b,u){href=new URL(u)}},addEventListener(k,fn){handlers[k]=fn},prompt(){}};
 class FixedDate extends Date{constructor(...args){super(...(args.length?args:['2026-11-05T12:00:00']))}static now(){return new Date('2026-11-05T12:00:00').getTime()}}
 const context={window,Date:FixedDate,document:{documentElement:{dataset:{}},querySelector:node,querySelectorAll:q=>q==='.nav button'?nav:[],getElementById:()=>({scrollIntoView(){}})},navigator:{},localStorage:{getItem:()=>null,setItem(){}},fetch:async path=>({ok:true,headers:{get:()=> 'application/json'},json:async()=>path==='/details.json'?details:data}),AbortController,URL,console,setTimeout,clearTimeout};vm.runInNewContext(script,context);await new Promise(resolve=>setImmediate(resolve));return {node,nav,go(h){href.hash=h;handlers.hashchange()}};
}
function card(app,id){return app.node('#grid').innerHTML.split('</article>').find(c=>c.includes(`id="show-${id}"`))}
function verify(app,id){const html=card(app,id);assert(html,`show ${id} rendered`);assert(html.includes('class="episode-list"')||html.includes('class="episode-box episode-list"'));assert(html.includes('</ul></details><p class="empty-detail">No comments</p></div>'));assert(!html.includes('<summary>Show comments</summary>'));assert(html.includes('class="episode-comments"'));}
(async()=>{
 const app=await boot();while(!app.node('#more').hidden)app.node('#more').handlers.click();for(const id of examples)verify(app,id);
 app.nav[1].handlers.click();while(!app.node('#more').hidden)app.node('#more').handlers.click();for(const id of examples)verify(app,id);
 app.nav[0].handlers.click();for(const id of examples){const show=data.items.find(x=>x.id===id);app.node('#search').value=show.title;app.node('#search').handlers.input();verify(app,id)}
 const featured=await boot('#featured-shows');for(const id of ['1056200096','1373812661','1380008439','1827500070'])verify(featured,id);
 for(const id of examples)verify(await boot('#show-'+id),id);
 const tal=await boot('#show-201671138'),html=card(tal,'201671138');assert(html.includes('<summary>Show comments</summary>'));assert(!html.includes('<p class="empty-detail">No comments</p>'));
 console.log('No comments appears immediately after the episode list in Browse, Latest, Featured, search and deep links for reported shows; episode comments and existing Show comments remain (DOM simulation).');
})().catch(e=>{console.error(e);process.exit(1)});
