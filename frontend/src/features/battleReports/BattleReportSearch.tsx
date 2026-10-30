import {useEffect,useState} from "react";
import type {Dispatch,SetStateAction} from "react";
export type BattleSearch={side:"my"|"hostile";match:"all"|"any";pilot_name:string;combat_corporation:string;alliance_name:string;system_name:string;class_key:string;type_id?:number;combatants:string};
export const emptyBattleSearch:BattleSearch={side:"my",match:"all",pilot_name:"",combat_corporation:"",alliance_name:"",system_name:"",class_key:"",combatants:""};
type Api=<T>(path:string,options?:RequestInit)=>Promise<T>;
type Options={classes:{key:string;name:string;section:string}[];types:{id:number;name:string}[];combatant_ranges:{key:string;label:string}[]};
export function BattleReportSearch({api,value,setValue,onSearch,onClear,disabled}:{api:Api;value:BattleSearch;setValue:Dispatch<SetStateAction<BattleSearch>>;onSearch:()=>void;onClear:()=>void;disabled:boolean}){
 const [options,setOptions]=useState<Options>({classes:[],types:[],combatant_ranges:[]}),[loading,setLoading]=useState(false),[error,setError]=useState("");
 useEffect(()=>{let active=true;const controller=new AbortController();setLoading(true);setError("");setOptions(old=>({...old,types:[]}));
  void api<Options>(`/battle-reports/report-search-options?class_key=${encodeURIComponent(value.class_key)}`,{signal:controller.signal}).then(result=>{if(active)setOptions(result);})
   .catch(e=>{if(active)setError(e instanceof Error?e.message:"Search options unavailable");}).finally(()=>{if(active)setLoading(false);});
  return()=>{active=false;controller.abort();};
 },[api,value.class_key]);
 function text(key:keyof BattleSearch,next:string){setValue(old=>({...old,[key]:next}));}
 return <form className="battle-detail-search" onSubmit={e=>{e.preventDefault();onSearch();}} aria-label="Find saved battles"><h4>Find a battle by remembered details</h4>
 <p>My Side is the saved report’s selected-pilot side. Hostile Side is its opposing side; third parties stay separate. Counts are unique recorded pilots across the battle, not simultaneous fleet strength.</p>
 <fieldset disabled={disabled} className="battle-search-grid">
 <label>Side to search<select value={value.side} onChange={e=>text("side",e.target.value)}><option value="my">My Side</option><option value="hostile">Hostile Side</option></select></label>
 <label>Pilot name<input value={value.pilot_name} maxLength={120} onChange={e=>text("pilot_name",e.target.value)} placeholder="Any part of a pilot name"/></label>
 <label>Combatant corporation<input value={value.combat_corporation} maxLength={120} onChange={e=>text("combat_corporation",e.target.value)} placeholder="Corporation on selected side"/></label>
 <label>Combatant alliance<input value={value.alliance_name} maxLength={120} onChange={e=>text("alliance_name",e.target.value)} placeholder="Alliance on selected side"/></label>
 <label>Ship class / deployable / structure<select value={value.class_key} onChange={e=>setValue(old=>({...old,class_key:e.target.value,type_id:undefined}))}><option value="">Any class or object</option>{["Ship classes","Deployables","Structures"].map(section=><optgroup key={section} label={section}>{options.classes.filter(c=>c.section===section).map(c=><option key={c.key} value={c.key}>{c.name}</option>)}</optgroup>)}</select></label>
 <label>Specific hull / deployable / structure<select value={value.type_id??""} disabled={!value.class_key||loading} onChange={e=>setValue(old=>({...old,type_id:e.target.value?Number(e.target.value):undefined}))}><option value="">{loading?"Loading objects…":value.class_key?"Any type in selected class":"Choose a class first"}</option>{options.types.map(t=><option key={t.id} value={t.id}>{t.name}</option>)}</select></label>
 <label>Involved pilots on selected side<select value={value.combatants} onChange={e=>text("combatants",e.target.value)}><option value="">Any number</option>{options.combatant_ranges.map(range=><option key={range.key} value={range.key}>{range.label}</option>)}</select></label>
 <label>System<input value={value.system_name} maxLength={120} onChange={e=>text("system_name",e.target.value)} placeholder="For example, Hagilua"/></label>
 <label>Combine detail filters<select value={value.match} onChange={e=>text("match",e.target.value)}><option value="all">Match all details (AND)</option><option value="any">Match any detail (OR)</option></select></label>
 </fieldset>
 <p>All details matches pilot, corporation, alliance and hull on the same recorded combatant or loss. Any detail accepts any of those clues on the chosen side. System, pilot-count range and generation dates always narrow the results. Gate names are not recorded by killmails.</p>
 {error&&<p role="alert">{error}</p>}<div className="battle-management-actions"><button type="submit" disabled={disabled}>Search saved reports</button><button type="button" disabled={disabled} onClick={onClear}>Clear battle details</button></div></form>;
}
