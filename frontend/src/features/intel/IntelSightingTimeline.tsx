import {EveItemName} from "../clientLinks/EveClientLinks";
import type {IntelReport} from "./types";
import {IntelShipLabel} from "./IntelShipLabel";
const utc=(value:string)=>new Date(value).toISOString().replace('T',' ').slice(0,19)+' UTC';
export function IntelSightingTimeline({report}:{report:IntelReport}){
 const sightings=report.sightings;
 return <><section className="panel stacked"><h3>Reported ship sightings ({sightings.total})</h3><p className="muted">{sightings.notice} This list follows the selected report dates and shows the latest {sightings.limit} entries.</p>
 <div className="intel-table-wrap"><table className="intel-sighting-table"><thead><tr><th>Sighting time (UTC)</th><th>System</th><th>Ship type</th><th>Kills / losses</th><th>Source / analyst</th></tr></thead><tbody>{sightings.rows.map(row=><tr key={row.id}><td>{utc(row.observed_at)}<small>{row.manual_time?"Manually entered time":"Report-run time"}</small></td><td><strong>{row.system_name}</strong><small>{row.region_name}</small></td><td><IntelShipLabel typeId={row.ship_type_id} name={row.ship_type_name}/></td><td>0 / 0</td><td>Analyst sighting<small>{row.observer}</small><small>Posted {utc(row.recorded_at)}</small></td></tr>)}</tbody></table></div>
 {!sightings.rows.length&&<p className="muted">No analyst sightings in this date range. Enter a system and optional ship beside the name search, then open or refresh the character report.</p>}</section>
 <section className="panel stacked"><h3>Daily activity timeline (UTC)</h3><p className="muted">Combat totals and manual sightings are separate columns. Sightings do not create killmails or change combat statistics.</p><div className="intel-table-wrap"><table><thead><tr><th>Date</th><th>Kills</th><th>Losses</th><th>Analyst sightings</th></tr></thead><tbody>{report.summary.timeline.map(row=><tr key={row.date}><td>{row.date}</td><td>{row.kills}</td><td>{row.losses}</td><td>{row.sightings??0}</td></tr>)}</tbody></table></div></section></>;
}
