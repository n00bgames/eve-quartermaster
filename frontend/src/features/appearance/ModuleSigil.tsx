import {
  Orbit, Route, ContactRound, GraduationCap, Wrench, Fingerprint, UsersRound, KeyRound,
  Radar, ScanLine, Crosshair, Telescope, ShieldAlert, ShoppingCart, ReceiptText, Store,
  Dice5, Gem, BadgeDollarSign, NotebookPen, Ship, ClipboardList, Workflow, PackageCheck,
  Factory, FlaskConical, Pickaxe, Globe2, Castle, Building2, Network, Boxes, Cpu,
  ScrollText, ChartNoAxesCombined, Flag, ShieldCheck, HeartPulse, Skull, Swords,
  CalendarDays, UserRoundPlus, UserRound, Settings2, FileSearch, type LucideIcon,
} from "lucide-react";

// Each destination has its own pictogram; sector frames add a second visual cue.
export const moduleIcons: Record<string, LucideIcon> = {
  overview:Orbit,navigation:Route,characters:ContactRound,skills:GraduationCap,fittings:Wrench,
  jump_clones:Fingerprint,roster:UsersRound,esi:KeyRound,local_scan:Radar,dscan:ScanLine,
  matchups:Crosshair,intel_reports:Telescope,local_threat:ShieldAlert,market:ShoppingCart,
  receipts:ReceiptText,exchange:Store,hypernet:Dice5,plex:Gem,bounty_analytics:BadgeDollarSign,
  notes:NotebookPen,ship_reports:Ship,inventory_reports:ClipboardList,industry_reports:Workflow,
  quartermaster:PackageCheck,manufacturing:Factory,research_projects:FlaskConical,mining:Pickaxe,
  planetary_industry:Globe2,structures:Castle,corporations:Building2,ownership:Network,assets:Boxes,
  industry:Cpu,contracts:ScrollText,analytics:ChartNoAxesCombined,fleet_assignments:Flag,
  doctrines:ShieldCheck,srp:HeartPulse,killboard:Skull,battle_reports:Swords,calendar_events:CalendarDays,
  recruiting:UserRoundPlus,profile:UserRound,settings:Settings2,audit:FileSearch,
};
const sectors: Record<string,string[]> = {
  crew:["characters","skills","jump_clones","roster","recruiting","profile"],
  intelligence:["local_scan","dscan","matchups","intel_reports","local_threat","killboard","battle_reports","doctrines","srp","fleet_assignments"],
  trade:["market","receipts","exchange","hypernet","plex","bounty_analytics","contracts"],
  industry:["ship_reports","inventory_reports","industry_reports","quartermaster","manufacturing","research_projects","mining","planetary_industry","structures","corporations","ownership","assets","industry"],
  systems:["settings","audit","esi","fittings","notes","analytics"],
};
export function moduleSector(module: string): string {
  return Object.entries(sectors).find(([,modules])=>modules.includes(module))?.[0] ?? "flight";
}
export function ModuleSigil({module,large=false}:{module:string;large?:boolean}) {
  const Icon=moduleIcons[module]??Orbit;
  return <span className={`module-sigil${large?" large":""}`} data-sector={moduleSector(module)} aria-hidden="true"><Icon size={large?30:19} strokeWidth={1.6}/></span>;
}
