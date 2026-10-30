import {useEffect,useMemo,useState} from "react";
import type {MarketHub} from "../../types/market";
type Api=<T>(path:string,options?:RequestInit)=>Promise<T>;
type PriceSide={price:number|null;units:number;orders:number};
type Summary={type_id:number;item:string;hub:{key:string;label:string;region_name?:string|null;region_id:number};fetched_at:string;history_expires_at:string|null;
 history:{date:string;volume:number;average:number;lowest:number;highest:number}[];history_error:string|null;orders_error:string|null;
 current:{buy:PriceSide;sell:PriceSide}|null;notice:string};
const isk=(value:number|null)=>value===null?"Unavailable":`${new Intl.NumberFormat(undefined,{minimumFractionDigits:2,maximumFractionDigits:2}).format(value)} ISK`;

export function MarketHistorySummary({api,typeId,itemName,hubs}:{api:Api;typeId:number;itemName:string;hubs:MarketHub[]}){
 const choices=useMemo(()=>hubs.filter(h=>h.available&&!h.npc_group&&h.region_id),[hubs]);
 const [hub,setHub]=useState(()=>choices[0]?.key??""),[data,setData]=useState<Summary|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(""),[refresh,setRefresh]=useState(0);
 const selected=choices.some(h=>h.key===hub)?hub:choices[0]?.key??"";
 useEffect(()=>{let active=true;const controller=new AbortController();setData(null);setError("");if(!selected)return;setBusy(true);
  void api<Summary>(`/market/items/${typeId}/history?hub=${encodeURIComponent(selected)}&limit=5`,{signal:controller.signal}).then(next=>{if(active)setData(next);}).catch(err=>{if(active)setError(err instanceof Error?err.message:"Market history unavailable.");}).finally(()=>{if(active)setBusy(false);});
  return()=>{active=false;controller.abort();};
 },[api,typeId,selected,refresh]);
 return <section className="market-history-summary" aria-label={`Market history for ${itemName}`}><h4>{itemName} · Market history</h4>
 {!choices.length?<p className="muted">Choose an individual trade hub for regional history; the NPC aggregate has no single market region.</p>:<>
 <div className="market-history-controls"><label>History market<select aria-label={`History market for ${itemName}`} value={selected} onChange={e=>setHub(e.target.value)}>{choices.map(h=><option key={h.key} value={h.key}>{h.label} — {h.region_name??`Region ${h.region_id}`}</option>)}</select></label><button disabled={busy} onClick={()=>setRefresh(n=>n+1)}>Refresh market history</button></div>
 {busy&&<p role="status">Loading completed trade history and current orders…</p>}{error&&<p role="alert">{error}</p>}
 {data&&<><p className="muted">Completed trades: <strong>{data.hub.region_name??`Region ${data.hub.region_id}`}</strong> · Latest five trading dates (UTC). All prices are per unit.</p>
 {data.history_error?<p role="alert">{data.history_error}</p>:data.history.length?<div className="table-wrap"><table><thead><tr><th>Date (UTC)</th><th>Units traded</th><th>Average</th><th>Lowest</th><th>Highest</th></tr></thead><tbody>{data.history.map(r=><tr key={r.date}><td>{r.date}</td><td>{r.volume.toLocaleString()}</td><td>{isk(r.average)}</td><td>{isk(r.lowest)}</td><td>{isk(r.highest)}</td></tr>)}</tbody></table></div>:<p>No completed trades were reported by ESI for this item in this region.</p>}
 <h4>Current orders · {data.hub.label}</h4>{data.orders_error?<p role="alert">{data.orders_error}</p>:data.current&&<div className="market-history-current">{([['sell','Cheapest sell'],['buy','Highest buy']] as const).map(([side,label])=><div key={side}><span>{label}</span><strong>{isk(data.current![side].price)}</strong><small>{data.current![side].price===null?"No orders at this hub":`${data.current![side].units.toLocaleString()} available/requested across ${data.current![side].orders} order(s) at this price`}</small></div>)}</div>}
 <p className="muted">{data.notice}</p><p className="muted">Checked {new Date(data.fetched_at).toLocaleString()}{data.history_expires_at?` · ESI history cache expires ${new Date(data.history_expires_at).toLocaleString()}`:""}. Refresh respects ESI caching; history can lag behind current orders.</p>
 </>}
 </>}
 </section>;
}
