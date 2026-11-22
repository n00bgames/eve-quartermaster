export const sortClips=(files:File[])=>files.slice().sort((a,b)=>a.name.localeCompare(b.name,undefined,{numeric:true,sensitivity:'base'}));
