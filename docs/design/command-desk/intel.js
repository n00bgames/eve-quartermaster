'use strict';
const sightings=[
 {time:'20:16',date:'01 NOV 2026',system:'Bei',hull:'Unknown ship type',kind:'observation',source:'Local scan',detail:'Fictional presence from a local scan. No hull was observed. This entry does not add a kill or loss.'},
 {time:'19:42',date:'01 NOV 2026',system:'Bei',hull:'Deimos',kind:'observation',source:'Manual sighting',detail:'Fictional manual sighting. An observer supplied the system and hull; the report does not verify the fit or infer an engagement.'},
 {time:'18:05',date:'01 NOV 2026',system:'Hagilur',hull:'Arazu',kind:'loss',source:'Imported loss',detail:'Fictional imported loss, included once in the sample combat totals. This does not establish the pilot’s current ship.'},
 {time:'16:28',date:'01 NOV 2026',system:'Evati',hull:'Unknown ship type',kind:'observation',source:'Manual sighting',detail:'Fictional sighting with a system and timestamp but no ship type. Unknown hull is retained rather than guessed.'},
];
const evidenceList=document.querySelector('#sightings');
function renderSightings(){
 const query=document.querySelector('#evidence-filter').value.trim().toLowerCase();
 const rows=sightings.filter(s=>`${s.system} ${s.hull} ${s.source}`.toLowerCase().includes(query));
 evidenceList.replaceChildren();
 for(const s of rows){
  const article=document.createElement('article');article.className=`sighting ${s.kind}`;
  const time=document.createElement('div');time.className='sighting-time';const b=document.createElement('b');b.textContent=s.time;const small=document.createElement('small');small.textContent=s.date;time.append(b,small);
  const mark=document.createElement('span');mark.className=`evidence-dot ${s.kind}`;mark.setAttribute('aria-hidden','true');
  const content=document.createElement('div');content.className='sighting-content';const h=document.createElement('h3');h.textContent=s.system;const hull=document.createElement('p');hull.textContent=s.hull;content.append(h,hull);
  const details=document.createElement('details');const summary=document.createElement('summary');summary.textContent=`${s.source} · evidence`;const p=document.createElement('p');p.textContent=s.detail;details.append(summary,p);content.append(details);article.append(time,mark,content);evidenceList.append(article);
 }
 if(!rows.length){const p=document.createElement('p');p.className='muted';p.textContent='No sample evidence matches that filter.';evidenceList.append(p);}
 document.querySelector('#evidence-count').textContent=`${rows.length} ENTR${rows.length===1?'Y':'IES'}`;
}
document.querySelector('#evidence-filter').addEventListener('input',renderSightings);
const tabButtons=[...document.querySelectorAll('[role=tab]')];
function setTab(button,focus=false){
 for(const tab of tabButtons){const active=tab===button;tab.setAttribute('aria-selected',String(active));tab.tabIndex=active?0:-1;document.querySelector(`#view-${tab.dataset.view}`).hidden=!active;}
 if(focus)button.focus();
}
for(const [index,button] of tabButtons.entries()){
 button.addEventListener('click',()=>setTab(button));
 button.addEventListener('keydown',event=>{let next;if(event.key==='ArrowRight')next=(index+1)%tabButtons.length;else if(event.key==='ArrowLeft')next=(index+tabButtons.length-1)%tabButtons.length;else if(event.key==='Home')next=0;else if(event.key==='End')next=tabButtons.length-1;if(next!==undefined){event.preventDefault();setTab(tabButtons[next],true);}});
}
const activity=[1,1,2,4,6,8,5,3,2,1,0,0,1,0,0,1,2,4,7,10,12,8,4,2];
for(const [hour,value] of activity.entries()){const bar=document.createElement('span');bar.style.setProperty('--height',`${Math.max(2,value/12*100)}%`);bar.title=`${String(hour).padStart(2,'0')}:00 UTC · ${value} fictional combat appearances`;bar.setAttribute('aria-hidden','true');document.querySelector('#activity-bars').append(bar);}
let notes=[{id:1,text:'Observed near the Bei gate. Hull not confirmed by the local scan; keep that separate from the earlier Deimos sighting.'},{id:2,text:'Example field note: do not infer current fittings or intent from this sample history.'}];
let editingNote=null;let nextNote=3;
const noteDialog=document.querySelector('#note-editor');
function editNote(id=null){editingNote=id;document.querySelector('#note-editor-title').textContent=id===null?'Add a sample note':'Edit sample note';document.querySelector('#note-text').value=notes.find(n=>n.id===id)?.text??'';noteDialog.showModal();document.querySelector('#note-text').focus();}
function renderNotes(){
 const list=document.querySelector('#field-notes');list.replaceChildren();
 for(const n of notes){const row=document.createElement('article');row.className='field-note';const p=document.createElement('p');p.textContent=n.text;const actions=document.createElement('div');const edit=document.createElement('button');edit.className='text-button';edit.textContent='Edit note ↗';edit.setAttribute('aria-label',`Edit sample note ${n.id}`);edit.addEventListener('click',()=>editNote(n.id));const remove=document.createElement('button');remove.className='text-button';remove.textContent='Remove from demo ×';remove.setAttribute('aria-label',`Remove sample note ${n.id}`);remove.addEventListener('click',()=>{notes=notes.filter(note=>note.id!==n.id);renderNotes();document.querySelector('#new-note').focus();});actions.append(edit,remove);row.append(p,actions);list.append(row);}
 if(!notes.length){const p=document.createElement('p');p.className='muted';p.textContent='No sample notes. Add one below.';list.append(p);}
 document.querySelector('#notes-count').textContent=String(notes.length).padStart(2,'0');
}
document.querySelector('#new-note').addEventListener('click',()=>editNote());
document.querySelector('#note-editor .close').addEventListener('click',()=>noteDialog.close());
document.querySelector('#note-form').addEventListener('submit',event=>{event.preventDefault();const text=document.querySelector('#note-text').value.trim();if(!text)return;if(editingNote===null)notes.push({id:nextNote++,text});else notes=notes.map(n=>n.id===editingNote?{...n,text}:n);renderNotes();noteDialog.close();document.querySelector('#new-note').focus();});
renderSightings();renderNotes();
