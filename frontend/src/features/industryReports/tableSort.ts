const collator=new Intl.Collator(undefined,{numeric:true,sensitivity:"base"});
export function sortReportRows<T extends Record<string,unknown>>(rows:T[],key:string|null,direction:"asc"|"desc"):T[]{
 if(!key)return rows;
 return rows.map((row,index)=>({row,index})).sort((a,b)=>{let x=a.row[key],y=b.row[key];const absent=(v:unknown)=>v===null||v===undefined||v==="";
 if(absent(x)||absent(y))return absent(x)&&absent(y)?a.index-b.index:absent(x)?1:-1;
 if(/(_at|_date)$/.test(key)){const dx=Date.parse(String(x)),dy=Date.parse(String(y));if(Number.isFinite(dx)&&Number.isFinite(dy)){x=dx;y=dy;}}
 const compared=typeof x==="number"&&typeof y==="number"?x-y:collator.compare(String(x),String(y));return (direction==="asc"?compared:-compared)||a.index-b.index;
 }).map(x=>x.row);
}
