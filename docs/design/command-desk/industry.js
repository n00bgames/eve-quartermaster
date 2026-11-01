'use strict';
const blueprints=[
 {name:'Antimatter Charge L',kind:'Original',me:10,te:20,runs:null,location:'Jita IV · Moon 4'},
 {name:'Deimos',kind:'Copy',me:2,te:4,runs:10,location:'Sample Assembly Yard'},
 {name:'Thorax',kind:'Original',me:8,te:16,runs:null,location:'Jita IV · Moon 4'},
 {name:'Warrior II',kind:'Copy',me:2,te:4,runs:100,location:'Sample Assembly Yard'},
 {name:'Fernite Carbide Reaction Formula',kind:'Formula',me:null,te:null,runs:null,location:'Sample Reaction Yard'},
 {name:'Vexor',kind:'Original',me:10,te:20,runs:null,location:'Jita IV · Moon 4'},
];
let sortKey='name',sortDirection=1;
function renderBlueprints(){
 const rows=[...blueprints].sort((a,b)=>{const x=a[sortKey],y=b[sortKey];if(x===null&&y===null)return a.name.localeCompare(b.name);if(x===null)return 1;if(y===null)return -1;return sortDirection*(typeof x==='number'?x-y:String(x).localeCompare(String(y)))||a.name.localeCompare(b.name);});
 const body=document.querySelector('#report-blueprints');body.replaceChildren();
 for(const item of rows){const row=document.createElement('tr');for(const field of ['name','kind','me','te','runs','location']){const cell=document.createElement('td');if(field==='name'){const label=document.createElement('strong');label.textContent=item[field];cell.append(label);}else cell.textContent=item[field]===null?'—':String(item[field]);row.append(cell);}body.append(row);}
 for(const button of document.querySelectorAll('[data-sort]')){const selected=button.dataset.sort===sortKey;button.closest('th').setAttribute('aria-sort',selected?(sortDirection===1?'ascending':'descending'):'none');button.querySelector('span').textContent=selected?(sortDirection===1?'↑':'↓'):'↕';}
}
for(const button of document.querySelectorAll('[data-sort]'))button.addEventListener('click',()=>{sortDirection=sortKey===button.dataset.sort?-sortDirection:1;sortKey=button.dataset.sort;renderBlueprints();});
const holdings=[
 {owner:'character',name:'Tritanium',quantity:1600000,location:'Jita IV · Moon 4'},
 {owner:'corporation',name:'Tritanium',quantity:2400000,location:'Sample Assembly Yard'},
 {owner:'character',name:'Pyerite',quantity:500000,location:'Jita IV · Moon 4'},
 {owner:'corporation',name:'Pyerite',quantity:700000,location:'Sample Assembly Yard'},
 {owner:'character',name:'Mechanical Parts',quantity:8000,location:'Jita IV · Moon 4'},
 {owner:'corporation',name:'Mechanical Parts',quantity:12000,location:'Sample Assembly Yard'},
 {owner:'corporation',name:'Consumer Electronics',quantity:12000,location:'Sample Assembly Yard'},
];
const totals=new Map();for(const row of holdings)totals.set(row.name,(totals.get(row.name)??0)+row.quantity);
const total=[...totals.values()].reduce((a,b)=>a+b,0);document.querySelector('#stock-total').textContent=total.toLocaleString('en-US');
for(const [name,quantity] of [...totals].sort((a,b)=>b[1]-a[1])){const row=document.createElement('div');row.className='stock-line';const label=document.createElement('span');label.textContent=name;const value=document.createElement('strong');value.textContent=quantity.toLocaleString('en-US');const track=document.createElement('div');track.className='stock-track';const bar=document.createElement('i');bar.style.width=`${quantity/Math.max(...totals.values())*100}%`;track.append(bar);row.append(label,value,track);document.querySelector('#stock-lines').append(row);}
function renderOwnership(){
 const filter=document.querySelector('#owner-filter').value;const body=document.querySelector('#ownership-rows');body.replaceChildren();
 const rows=holdings.filter(h=>filter==='all'||h.owner===filter);let group='';
 for(const h of rows.slice().sort((a,b)=>a.owner.localeCompare(b.owner)||a.name.localeCompare(b.name))){if(group!==h.owner){group=h.owner;const row=document.createElement('tr');row.className='ownership-group';const cell=document.createElement('th');cell.colSpan=3;cell.scope='rowgroup';cell.textContent=group==='character'?'Character owned':'Corporation owned';row.append(cell);body.append(row);}const row=document.createElement('tr');for(const value of [h.name,h.location,h.quantity.toLocaleString('en-US')]){const cell=document.createElement('td');cell.textContent=value;row.append(cell);}row.lastChild.className='quantity';body.append(row);}
 document.querySelector('#ownership-summary').textContent=`${rows.length} sample holdings · ${rows.reduce((sum,h)=>sum+h.quantity,0).toLocaleString('en-US')} units in this ownership view. Overall stock totals above always include both groups.`;
}
document.querySelector('#owner-filter').addEventListener('change',renderOwnership);
const privacyDialog=document.querySelector('#privacy-dialog');document.querySelector('#privacy-note').addEventListener('click',()=>privacyDialog.showModal());document.querySelector('#close-privacy').addEventListener('click',()=>privacyDialog.close());
renderBlueprints();renderOwnership();
