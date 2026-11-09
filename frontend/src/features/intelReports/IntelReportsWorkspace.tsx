import {IntelReportsPage} from "../intel/IntelReportsPage";
import {IntelReportBuilder} from "./IntelReportBuilder";
import type {ApiClient} from "./types";
import "./intelReports.css";

export function IntelReportsWorkspace({api}:{api:ApiClient}) {
 const dossier=/^#intel\/\d+$/.test(location.hash)||location.hash.startsWith("#intel/dossiers")||location.hash.startsWith("#intel-notes");
 return <section className="intel-report-workspace intel-page"><nav className="intel-tabs" aria-label="Intel workspace"><a className={!dossier?"active":""} href="#intel">Run / share a report</a><a className={dossier?"active":""} href="#intel/dossiers">Saved dossiers and notes</a></nav>{dossier?<IntelReportsPage api={api}/>:<IntelReportBuilder api={api}/>}</section>;
}
