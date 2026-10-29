import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mergePanelOrder,navigationWithDefaults,defaultNavigation,addShortcut,removeShortcut,moveModule,move,orderedKeys,presets,themeError} from '../src/features/appearance/model.ts';
import {sortReportRows} from '../src/features/industryReports/tableSort.ts';
test('navigation defaults add new modules and discard unknown or duplicate entries',()=>{
 const groups=navigationWithDefaults([{id:'intel',name:'Operations',modules:['local_scan','local_scan','made_up']},{id:'intel',name:'Duplicate',modules:[]}]);
 const flat=groups.flatMap(g=>g.modules);assert.equal(flat.length,new Set(flat).size);assert.deepEqual(new Set(flat),new Set(defaultNavigation.flatMap(g=>g.modules)));assert.equal(groups[0].name,'Operations');
});
test('module and group moves keep exactly one of each, and preserve hidden modules',()=>{
 const initial=navigationWithDefaults();const groups=moveModule(initial,'market','finance','intel','local_scan');assert.equal(groups.find(g=>g.id==='intel')!.modules[0],'market');assert.equal(groups.flatMap(g=>g.modules).filter(x=>x==='market').length,1);assert.deepEqual(initial,defaultNavigation);assert.equal(move(groups,0,2)[2].id,'main');
});
test('panel order preserves new and temporarily absent panels without duplicates',()=>{assert.deepEqual(orderedKeys(['a','b','c'],['b','absent','b']),['b','a','c']);});
test('all presets remain readable and invalid colors rejected',()=>{for(const theme of Object.values(presets))assert.equal(themeError(theme),'');assert.ok(themeError({...presets.Daylight,text:'#ffffff'}));assert.ok(themeError({...presets.Daylight,accent:'url(evil)'}));});
test('numeric sorting covers all 2501 rows before pagination and does not mutate',()=>{const rows=Array.from({length:2501},(_,i)=>({quantity:i,item:`Item ${i}`}));const sorted=sortReportRows(rows,'quantity','desc');assert.equal(sorted[0].quantity,2500);assert.equal(sorted.slice(100,200)[0].quantity,2400);assert.equal(rows[0].quantity,0);});
test('natural text, dates, missing values and ties',()=>{const rows=[{item:'Item 10',n:2,end_date:'2026-10-29T10:00:00+02:00'},{item:'Item 2',n:2,end_date:'2026-10-29T09:00:00Z'},{item:'',n:null,end_date:null}];assert.equal(sortReportRows(rows,'item','asc')[0].item,'Item 2');assert.equal(sortReportRows(rows,'end_date','asc')[0].item,'Item 10');assert.equal(sortReportRows(rows,'n','desc')[2].n,null);assert.equal(sortReportRows(rows,'n','desc')[0].item,'Item 10');});

test('saving a visible panel move retains temporarily hidden positions',()=>{assert.deepEqual(mergePanelOrder(['a','hidden','b'],['b','a','new']),['b','hidden','a','new']);});
test('normalizing maximum custom groups stays within the server bound',()=>{const groups=navigationWithDefaults(Array.from({length:20},(_,i)=>({id:`custom-${i}`,name:'Custom',modules:[]})));assert.equal(groups.length,20);assert.equal(groups.flatMap(g=>g.modules).length,defaultNavigation.flatMap(g=>g.modules).length);});

test('Quicklaunch survives normalization and removal preserves the original link',()=>{
 const original=navigationWithDefaults();
 const initial=[{id:'quick',name:'Quicklaunch',modules:[]},...original];
 const added=addShortcut(addShortcut(initial,'local_scan','quick'),'market','quick');
 const saved=navigationWithDefaults(JSON.parse(JSON.stringify(added)));
 assert.deepEqual(saved[0].modules,['local_scan','market']);
 assert.ok(saved.find(g=>g.id==='intel')!.modules.includes('local_scan'));
 assert.ok(saved.find(g=>g.id==='finance')!.modules.includes('market'));
 assert.deepEqual(addShortcut(saved,'market','quick'),saved);
 assert.deepEqual(addShortcut(saved,'unknown','quick'),saved);
 const removed=navigationWithDefaults(removeShortcut(saved,'market','quick'));
 assert.deepEqual(removed[0].modules,['local_scan']);
 assert.ok(removed.find(g=>g.id==='finance')!.modules.includes('market'));
 assert.deepEqual(removeShortcut(removed,'market','finance'),removed);
 assert.deepEqual(original,defaultNavigation);
});

test('moving a shortcut does not erase copies in other sections or create duplicate destinations',()=>{
 let groups=[{id:'quick',name:'Quicklaunch',modules:['market','local_scan']},...navigationWithDefaults()];
 groups=moveModule(groups,'market','quick','intel','local_scan');
 assert.ok(groups.find(g=>g.id==='finance')!.modules.includes('market'));
 assert.deepEqual(groups[0].modules,['local_scan']);
 assert.equal(groups.find(g=>g.id==='intel')!.modules[0],'market');
 groups=moveModule(groups,'market','intel','finance','exchange');
 assert.equal(groups.flatMap(g=>g.modules).filter(m=>m==='market').length,1);
 assert.equal(groups.find(g=>g.id==='finance')!.modules.filter(m=>m==='market').length,1);
 assert.ok(groups.find(g=>g.id==='intel')!.modules.includes('local_scan'));
 assert.deepEqual(groups[0].modules,['local_scan']);
});

test('normalization keeps cross-group shortcuts and temporarily permission-hidden entries',()=>{
 const groups=navigationWithDefaults([{id:'quick',name:'Quicklaunch',modules:['local_scan','local_scan','audit']},...defaultNavigation]);
 assert.deepEqual(groups[0].modules,['local_scan','audit']);
 assert.ok(groups.find(g=>g.id==='account')!.modules.includes('audit'));
 assert.equal(groups.flatMap(g=>g.modules).filter(m=>m==='local_scan').length,2);
 assert.deepEqual(navigationWithDefaults(groups),groups);
});
