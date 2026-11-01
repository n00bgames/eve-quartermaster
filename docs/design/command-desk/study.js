'use strict';
// Preview-only preferences, isolated from EQM account settings.
const paletteSelect=document.querySelector('#palette');
const densityToggle=document.querySelector('#compact');
try {
 const palette=sessionStorage.getItem('eqm-design-palette');
 if(['brass','blue','paper'].includes(palette)){document.documentElement.dataset.palette=palette;paletteSelect.value=palette;}
 const compact=sessionStorage.getItem('eqm-design-compact')==='true';
 document.body.classList.toggle('compact',compact);densityToggle.checked=compact;
} catch { /* Browser storage may be unavailable for a local file. */ }
paletteSelect.addEventListener('change',()=>{
 document.documentElement.dataset.palette=paletteSelect.value;
 try{sessionStorage.setItem('eqm-design-palette',paletteSelect.value);}catch{}
});
densityToggle.addEventListener('change',()=>{
 document.body.classList.toggle('compact',densityToggle.checked);
 try{sessionStorage.setItem('eqm-design-compact',String(densityToggle.checked));}catch{}
});
document.querySelector('nav[aria-label="Design studies"] .selected')?.setAttribute('aria-current','page');
