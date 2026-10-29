export type Theme = {background:string;panel:string;text:string;muted:string;accent:string;border:string};
export type NavGroup = {id:string;name:string;modules:string[]};
export type Preferences = {theme?:Theme;navigation?:NavGroup[];layouts?:Record<string,string[]>};
export const presets:Record<string,Theme> = {
  "EQM dark":{background:"#101215",panel:"#191e25",text:"#f5f7fa",muted:"#aab4c2",accent:"#e8b84d",border:"#3b4654"},
  "Deep space":{background:"#0b1425",panel:"#15243c",text:"#eff6ff",muted:"#a9bedb",accent:"#72b7ff",border:"#3c577b"},
  "Emerald":{background:"#0b1814",panel:"#142b23",text:"#edf9f2",muted:"#acd2bf",accent:"#75dfb3",border:"#416859"},
  "Amethyst":{background:"#191221",panel:"#2a2036",text:"#f8f0ff",muted:"#c6b2d8",accent:"#c39bff",border:"#635071"},
  "Daylight":{background:"#edf1f5",panel:"#ffffff",text:"#182330",muted:"#4b6075",accent:"#245e9e",border:"#b3c0cd"},
};
export const defaultNavigation:NavGroup[] = [
 {id:"main",name:"",modules:["overview","navigation"]},
 {id:"characters",name:"Character Functions",modules:["characters","skills","fittings","jump_clones","roster","esi"]},
 {id:"intel",name:"Intel",modules:["local_scan","dscan","intel_reports","local_threat"]},
 {id:"finance",name:"Finance & Trade",modules:["market","exchange","hypernet","plex","bounty_analytics"]},
 {id:"industry",name:"Inventory & Industry",modules:["notes","ship_reports","inventory_reports","industry_reports","quartermaster","manufacturing","research_projects","mining","planetary_industry","corporations","ownership","assets","industry","contracts","analytics"]},
 {id:"community",name:"Fleet & Community",modules:["fleet_assignments","doctrines","srp","killboard","battle_reports","calendar_events","recruiting"]},
 {id:"account",name:"Account & Admin",modules:["profile","settings","audit"]},
];
export function navigationWithDefaults(saved?:NavGroup[]):NavGroup[]{
 const known=new Set(defaultNavigation.flatMap(g=>g.modules)),seen=new Set<string>(),groups=new Set<string>();
 // A module may appear in several groups as a shortcut, but only once in each group.
 const out=(saved??defaultNavigation).filter(g=>{if(groups.has(g.id))return false;groups.add(g.id);return true;}).map(g=>{
  const local=new Set<string>();
  return {...g,modules:g.modules.filter(m=>{if(!known.has(m)||local.has(m))return false;local.add(m);seen.add(m);return true;})};
 });
 for(const group of defaultNavigation){const missing=group.modules.filter(m=>!seen.has(m));if(!missing.length)continue;const target=out.find(g=>g.id===group.id);if(target)target.modules.push(...missing);else if(out.length<20)out.push({...group,modules:missing});else out[0].modules.push(...missing);}
 return out;
}
export function move<T>(items:T[],from:number,to:number):T[]{const out=[...items];if(from<0||from>=out.length||to<0||to>=out.length)return out;out.splice(to,0,out.splice(from,1)[0]);return out;}
export function addShortcut(groups:NavGroup[],module:string,target:string):NavGroup[]{
 if(!defaultNavigation.some(g=>g.modules.includes(module)))return groups;
 return groups.map(g=>g.id===target&&!g.modules.includes(module)?{...g,modules:[...g.modules,module]}:g);
}
export function removeShortcut(groups:NavGroup[],module:string,source:string):NavGroup[]{
 // Keep at least one navigation entry, including entries temporarily hidden by permissions.
 if(groups.filter(g=>g.modules.includes(module)).length<2)return groups;
 return groups.map(g=>g.id===source?{...g,modules:g.modules.filter(m=>m!==module)}:g);
}
export function moveModule(groups:NavGroup[],module:string,source:string,target:string,before?:string):NavGroup[]{
 if(module===before||!groups.some(g=>g.id===source&&g.modules.includes(module))||!groups.some(g=>g.id===target))return groups;
 // Move this occurrence only. A destination that already has the link keeps a single copy.
 const out=groups.map(g=>({...g,modules:g.modules.filter(m=>m!==module||(g.id!==source&&g.id!==target))}));
 const destination=out.find(g=>g.id===target)!;
 const index=before?destination.modules.indexOf(before):-1;destination.modules.splice(index<0?destination.modules.length:index,0,module);return out;
}
export function orderedKeys(available:string[],saved?:string[]):string[]{return [...new Set([...(saved??[]).filter(id=>available.includes(id)),...available])];}
export function luminance(hex:string){const rgb=[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);return rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722;}
export function contrast(a:string,b:string){const x=luminance(a),y=luminance(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);}
export function themeError(theme:Theme){if(Object.values(theme).some(c=>!/^#[0-9a-f]{6}$/i.test(c)))return "Use six-digit hex colors.";if(Math.min(contrast(theme.text,theme.background),contrast(theme.text,theme.panel))<4.5)return "Text needs 4.5:1 contrast against both backgrounds.";if(Math.min(contrast(theme.muted,theme.background),contrast(theme.muted,theme.panel))<3)return "Secondary text needs 3:1 contrast against both backgrounds.";return "";}

export function mergePanelOrder(saved:string[]|undefined,visible:string[]):string[]{
 const pending=[...visible],present=new Set(visible);const out=(saved??[]).map(id=>present.has(id)?pending.shift()!:id);return [...new Set([...out,...pending])];
}
