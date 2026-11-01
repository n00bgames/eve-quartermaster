'use strict';
// Explicitly synthetic, self-contained design data. Never connects to EQM/ESI.
const assets=[
 {name:'Deimos',kind:'Hull',location:'Jita IV · Moon 4',owner:'Character owned',quantity:3,mark:'◈'},
 {name:'Tritanium',kind:'Material',location:'Amarr VIII · Emperor Family',owner:'Corporation owned',quantity:18420000,mark:'▱'},
 {name:'Neutron Blaster Cannon II',kind:'Module',location:'Jita IV · Moon 4',owner:'Character owned',quantity:24,mark:'⌁'},
 {name:'Mechanical Parts',kind:'Material',location:'Amarr VIII · Emperor Family',owner:'Corporation owned',quantity:12600,mark:'⊞'},
 {name:'Warrior II',kind:'Drone',location:'Bei · Sample hangar',owner:'Character owned',quantity:250,mark:'⋈'},
 {name:'Navy Cap Booster 3200',kind:'Charge',location:'Jita IV · Moon 4',owner:'Character owned',quantity:640,mark:'▥'},
];
const dialog=document.querySelector('#detail');
function show(title,paragraphs,kicker='DESIGN STUDY / SAMPLE DATA'){
 document.querySelector('#dialog-title').textContent=title;
 document.querySelector('#dialog-kicker').textContent=kicker;
 const body=document.querySelector('#dialog-body');body.replaceChildren();
 for(const text of paragraphs){const p=document.createElement('p');p.textContent=text;body.append(p);}
 dialog.showModal();
}
function render(){
 const query=document.querySelector('#filter').value.trim().toLowerCase();
 const matches=assets.filter(a=>`${a.name} ${a.kind} ${a.location} ${a.owner}`.toLowerCase().includes(query));
 const body=document.querySelector('#asset-rows');body.replaceChildren();
 for(const a of matches){
  const row=document.createElement('tr');
  const item=document.createElement('td');
  const name=document.createElement('div');name.className='asset-name';
  const mark=document.createElement('span');mark.className=`item-mark ${a.kind==='Material'?'material':''}`;mark.textContent=a.mark;mark.setAttribute('aria-hidden','true');
  const label=document.createElement('div');const strong=document.createElement('strong');strong.textContent=a.name;const small=document.createElement('small');small.textContent=a.location;label.append(strong,small);name.append(mark,label);item.append(name);
  const owner=document.createElement('td');owner.className='owner';owner.textContent=a.owner;
  const qty=document.createElement('td');qty.className='quantity';qty.textContent=a.quantity.toLocaleString('en-US');
  const action=document.createElement('td');const open=document.createElement('button');open.className='row-open';open.textContent='↗';open.setAttribute('aria-label',`View sample ${a.name}`);open.addEventListener('click',()=>show(a.name,[`${a.quantity.toLocaleString('en-US')} units · ${a.owner}.`,`${a.location}. This is an illustrative record, not a real holding.`,`In the application, this would open the existing item and location context, keeping the full manifest within reach.`],'SAMPLE MANIFEST / ITEM DETAIL'));action.append(open);row.append(item,owner,qty,action);body.append(row);
 }
 document.querySelector('#shown').textContent=`${matches.length} RECORD${matches.length===1?'':'S'}`;
 document.querySelector('#empty').hidden=matches.length>0;
}
document.querySelector('#filter').addEventListener('input',render);
document.querySelector('#reset').addEventListener('click',()=>{document.querySelector('#filter').value='';render();document.querySelector('#filter').focus();});
document.querySelector('#dismiss').addEventListener('click',()=>dialog.close());
document.querySelector('#data-note').addEventListener('click',()=>show('A desk, not a deployment.', ['Everything on this page is sample data. It makes no network requests and has no account connection, sync, saved preferences or live game actions.','The overview totals use fields EQM already has. The blueprint composition is a proposed presentation that would need a complete, permission-scoped aggregate—not a count of loaded rows.','This study explores the layout and identity before changing the actual application.']));
document.querySelector('#library-note').addEventListener('click',()=>show('Give the library its own voice.', ['A quieter blue separates industry from the brass workspace. The segmented strip represents the actual proportions of this sample library: 1,920 originals, 680 copies and 84 formulas.','Production integration must preserve record counts versus item quantities, existing blueprint details, permissions and the user’s chosen theme.']));
document.querySelector('#event-note').addEventListener('click',()=>show('Small hulls. Questionable decisions.', ['Sample event · November 2 · 19:00 UTC.','This demonstrates an unboxed calendar row. In the app it would open the existing fleet event; this standalone study creates no registration or attendance record.'],'SAMPLE FLEET CALENDAR'));
document.querySelector('#principles').addEventListener('click',()=>show('The quartermaster’s desk.', ['Use alignment, spacing, typography and rules before adding a container. Give enclosed surfaces a job: interaction, selection or a genuinely distinct information type.','The cargo-yard drawing is an original, code-native vector asset. Decorative geometry is hidden from controls; labels and tables stay ordinary readable text.','Retain keyboard access, reduced-motion support, light and dark colors, custom branding and draggable panel identities. Intel and Industry should share this language, with compositions designed for their own tasks.'],'EQM / VISUAL PRINCIPLES'));
render();
