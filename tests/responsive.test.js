const fs=require('fs'),assert=require('assert');
const page=fs.readFileSync('dist/index.html','utf8');
assert(page.includes('@media(min-width:601px) and (max-width:1000px)'));
assert(page.includes('grid-template-columns:20px minmax(135px,1.2fr) minmax(0,1fr) 200px;column-gap:10px'));
assert(page.includes('@media(min-width:801px) and (max-width:1000px)'));
assert(page.includes('.app{grid-template-columns:190px minmax(0,1fr)}'));
assert(page.includes('.topbar,.content{max-width:1320px;margin-left:auto;margin-right:auto;padding-left:40px;padding-right:40px}'));
assert(page.includes('.card-details{width:100%;max-width:860px}'));
assert(page.includes('@media(min-width:1101px)'));
assert(page.includes('.feature>a{grid-column:2;grid-row:1 / span 3;min-width:0}'));
assert(page.includes('.episode-box ul{padding:0 0 0 16px;margin:0;list-style:none}'));
assert(page.includes('.episode-content{padding:12px 0 2px 18px}'));
// Minimum track widths, gaps and row padding fit at the narrow edge of each desktop/tablet breakpoint.
for(const width of [601,800,801,1000,1001,1101,1919]){
 const sidebar=width>=1001?250:width>=801?190:0;
 const appOverhead=width>=801?24:0;
 const main=width-sidebar-appOverhead;
 const content=width>=1001?Math.min(main,1320)-80:main*.916;
 const minimum=width>=1001?28+210+220+60+24:20+135+200+30+24;
 assert(content>=minimum,`${width}px: available ${content}, minimum ${minimum}`);
}
console.log('Responsive CSS: tablet tracks fit at breakpoint edges, desktop content is bounded, feature layout and nested indentation retained (CSS inspection; not a browser test).');
