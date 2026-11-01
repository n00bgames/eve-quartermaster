import type {JourneySystem,Visit} from './types.ts';

export function visitCounts(visits:Visit[]):Map<number,number>{
 const counts=new Map<number,number>();for(const v of visits)counts.set(v.system_id,(counts.get(v.system_id)??0)+1);return counts;
}
export function replayFrame(visits:Visit[],cursor:number|null):Visit[]{
 return cursor===null?visits:visits.slice(0,Math.max(0,Math.min(visits.length,cursor+1)));
}
export function projectSystems(systems:JourneySystem[],width=1000,height=560):{system:JourneySystem;x:number;y:number}[]{
 const located=systems.filter(s=>s.x!==null&&s.z!==null&&Number.isFinite(s.x)&&Number.isFinite(s.z));
 if(!located.length)return [];
 const xs=located.map(s=>s.x!),zs=located.map(s=>s.z!);
 const minX=Math.min(...xs),maxX=Math.max(...xs),minZ=Math.min(...zs),maxZ=Math.max(...zs);
 const scale=Math.min(Math.max(100,width-110)/(maxX-minX||1),Math.max(100,height-110)/(maxZ-minZ||1));
 return located.map(system=>({system,x:width/2+(system.x!-(minX+maxX)/2)*scale,y:height/2-(system.z!-(minZ+maxZ)/2)*scale}));
}
