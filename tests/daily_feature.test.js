const fs=require('fs'),vm=require('vm'),assert=require('assert');
const script=fs.readFileSync('dist/app.js','utf8'),data=JSON.parse(fs.readFileSync('dist/data.json')),details=JSON.parse(fs.readFileSync('dist/details.json'));
async function boot(start,reverse=false){
 let clock=new Date(start).getTime(),nextTimer=0;const timers=new Map(),nodes={};
 class LocalDate extends Date{constructor(...args){if(args.length)super(...args);else super(clock)}static now(){return clock}}
 function element(k){return nodes[k]??={disabled:false,hidden:false,value:'',innerHTML:'',textContent:'',dataset:{},handlers:{},classList:{toggle(){},add(){},remove(){}},addEventListener(n,f){this.handlers[n]=f},setAttribute(){}}}
 const nav=['browse','latest'].map(v=>{const e=element(v);e.dataset.view=v;return e});
 const snapshot=reverse?{...data,items:[...data.items].reverse()}:data;
 const context={document:{documentElement:{dataset:{}},querySelector:element,querySelectorAll:q=>q==='.nav button'?nav:[]},localStorage:{getItem:()=>null,setItem(){}},fetch:async path=>({ok:true,headers:{get:()=> 'application/json'},json:async()=>path==='/details.json'?details:snapshot}),Date:LocalDate,AbortController,URL,Math,console,setTimeout:(fn,ms)=>{const id=++nextTimer;timers.set(id,{fn,ms});return id},clearTimeout:id=>timers.delete(id)};
 vm.runInNewContext(script,context);await new Promise(resolve=>setImmediate(resolve));
 return {nodes,nav,element,timers,setDate:value=>{clock=new Date(value).getTime()}};
}
function selected(b){const html=b.nodes['#featured'].innerHTML;assert.equal((html.match(/class="feature"/g)||[]).length,1);const match=html.match(/data-show-id="([^"]+)"/);assert(match);return match[1]}
(async()=>{
 assert(!script.includes('Math.random('));
 const first=await boot('2026-11-05T01:00:00'),refresh=await boot('2026-11-05T21:30:00'),otherOrder=await boot('2026-11-05T12:00:00',true),next=await boot('2026-11-06T01:00:00');
 const today=selected(first);assert.equal(selected(refresh),today);assert.equal(selected(otherOrder),today);assert.notEqual(selected(next),today);
 first.nav[1].handlers.click();first.nav[0].handlers.click();assert.equal(selected(first),today);
 const midnight=[...first.timers.values()].find(t=>t.ms>8000);assert(midnight);first.setDate('2026-11-06T00:01:00');midnight.fn();assert.equal(selected(first),selected(next));
 for(const [a,b] of [['2026-12-31T12:00:00','2027-01-01T12:00:00'],['2028-02-29T12:00:00','2028-03-01T12:00:00']])assert.notEqual(selected(await boot(a)),selected(await boot(b)));
 if(process.env.DAILY_REPORT==='1'){const current=await boot(new Date());const id=selected(current),show=data.items.find(x=>String(x.id)===id);console.log('Current local selection:',show.title,'ID:',id)}
 console.log('Daily choice: same date and reordered pool stable; next day, year boundary, leap day and midnight refresh change correctly (DOM simulation)');
})().catch(e=>{console.error(e);process.exit(1)});
