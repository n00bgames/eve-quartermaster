import type {IntelReport} from "./types";

const escape=(value:unknown)=>String(value??"Unknown").replace(/[\\`*_{}\[\]<>|]/g,"\\$&").replace(/[\r\n]+/g," ");
const utc=(value:string)=>new Date(value).toISOString().replace("T"," ").replace(".000Z"," UTC");

export function combatDossierFilename(report:IntelReport):string {
 return `eqm-combat-${report.subject.kind}-${report.subject.eve_id}-${report.window.to_at.slice(0,10)}.md`;
}

/** Explicit public-combat projection: never serialize the staff response. */
export function combatDossierMarkdown(report:IntelReport):string {
 const s=report.summary,subject=report.subject,f=report.association_filters;
 const lines=[`# ${escape(subject.name)} combat dossier`,"",`[${escape(subject.kind)} ${subject.eve_id} on zKillboard](https://zkillboard.com/${subject.kind}/${subject.eve_id}/)`,"",`Window: ${utc(report.window.from_at)} through ${utc(report.window.to_at)} (exclusive end).`,"",
 "**Public killmail observations only. Combat times are not online hours. No records does not mean inactive. Co-attacker appearances do not prove fleet membership, an agreement, or common ownership. Collection gaps and page limits can omit activity.**", "",
 `Observed PvP kills: ${s.kills}. Observed PvP losses: ${s.losses}. Retained killmails: ${report.coverage.loaded_killmails}.`,
 `Analysis capped: ${report.coverage.analysis_limited?"yes":"no"}. Collection completeness is not guaranteed.`,"", "## Recorded UTC activity","", "| UTC hour | PvP killmail appearances |","|---:|---:|"];
 for(const row of s.utc_hours)lines.push(`| ${String(row.hour).padStart(2,"0")}:00 | ${row.appearances} |`);
 lines.push("","## Recurring co-attackers","",`Applied association filters: ${f?.max_attackers?`at most ${f.max_attackers} named attackers`:"all fight sizes"}; at least ${f?.min_days??1} shared UTC day(s); ranked by ${f?.sort==="days"?"shared UTC days":"shared kills"}. Combat totals use the full retained sample.`,"","| Pilot | Shared kills | Shared UTC days | Estimated engagements |","|---|---:|---:|---:|");
 const associates=s.associates.filter(row=>row.kind==="character");
 for(const row of associates)lines.push(`| [${escape(row.name)}](https://zkillboard.com/character/${row.id}/) | ${row.kills} | ${row.distinct_days} | ${row.estimated_engagements} |`);
 if(!associates.length)lines.push("| No matching recorded co-attackers | — | — | — |");
 lines.push("","Engagements group same-system appearances separated by no more than 30 minutes. Shared-kill percentages in EQM use all subject PvP kills.","","## Recent retained combat evidence","","| UTC | Side | Killmail |","|---|---|---|");
 for(const row of s.evidence)lines.push(`| ${utc(row.time)} | ${escape(row.side)}${row.npc_only?"; NPC-only":""} | [${row.id}](https://zkillboard.com/kill/${row.id}/) |`);
 if(!s.evidence.length)lines.push("| No retained records in this window | — | — |");
 lines.push("",report.definitions.evidence??"Recent evidence can be capped.","", "Source: retained public zKill discovery and ESI killmails in EQM. Notes, sightings, authorized ESI, account identity and Journey history are excluded.");
 return lines.join("\n")+"\n";
}

export function downloadCombatDossier(report:IntelReport):void {
 const url=URL.createObjectURL(new Blob([combatDossierMarkdown(report)],{type:"text/markdown;charset=utf-8"}));
 const anchor=document.createElement("a");anchor.href=url;anchor.download=combatDossierFilename(report);anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
