import type {ReportMeta, ScanContext, ScanReport} from "../localScan/types";
export type DScanRow = {type_id:number|null;type_name:string;group_name:string;category:string;observed:number;manual:number;count:number;unit_mass_kg:number|null};
export type DScanMeta = ReportMeta & {object_count:number;ship_count:number};
export type DScanReport = DScanMeta & {objects:{type_id:number|null;type_name:string;name:string;distance:string;resolved:boolean}[];rows:DScanRow[];classes:{name:string;count:number}[];observed_ship_count:number;manual_ship_count:number;manual_recons:Record<string,number>;ship_mass_kg:number;mass_unknown_count:number;mass_complete:boolean;unresolved_count:number;system:{id:number;name:string}|null;local_scan:Omit<ScanReport,keyof ReportMeta>|null;warnings:string[];ignored:{line:number;reason:string}[];source:string};
export type DScanContext = ScanContext & {max_objects:number;recon_types:string[]};
