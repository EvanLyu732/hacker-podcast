const fs=require('fs'),assert=require('assert');
const page=fs.readFileSync('dist/index.html','utf8');
const marker='/* Keep desktop cards grouped like the compact mobile layout. */';
assert(page.includes(marker));const compact=page.slice(page.indexOf(marker),page.indexOf('</style>'));
assert(compact.includes('@media(min-width:601px)'));
assert(compact.includes('.topbar,.content{max-width:980px;'));
assert(compact.includes('.list-head,.card-number{display:none}'));
assert(compact.includes('.card{grid-template-columns:88px minmax(0,1fr);grid-template-rows:40px 20px 28px auto;'));
assert(compact.includes('.show-info{grid-column:1 / -1;grid-row:1 / 4;'));
assert(compact.includes('.episode-info{grid-column:2;grid-row:2;'));
assert(compact.includes('.card-actions{grid-column:2;grid-row:3;'));
assert(compact.includes('.card-details{grid-column:1 / -1;grid-row:4;'));
assert(compact.includes('.feature{display:block;padding:18px 18px 0}'));
assert(compact.includes('.feature-art.no-image{grid-template-columns:minmax(0,1fr) 42px}'));
assert(page.includes('.episode-box ul{padding:0 0 0 16px;margin:0;list-style:none}'));
assert(page.includes('.episode-content{padding:12px 0 2px 18px}'));
// The fixed cover and at least 200px of text fit even at the narrowest desktop breakpoint.
for(const width of [601,800,801,1000,1101,1919]){
 const sidebar=width>=1001?250:width>=801?190:0,overhead=width>=801?24:0,main=width-sidebar-overhead;
 const content=width>=1001?Math.min(main,980)-80:Math.min(main,980)*.916;
 assert(content>=88+12+200+24,`${width}px: content width ${content}`);
}
console.log('Responsive CSS: compact cover-side layout at desktop/tablet widths, mobile indentation preserved (CSS inspection, not a browser test).');
