import type {ReactElement,ReactNode} from "react";
import {LayoutRegion} from "../appearance/LayoutRegion";
import {useInterfaceStyle} from "../appearance/AppearanceProvider";
import {SupportCard} from "../clientLinks/EveClientLinks";
import {InterfaceArtwork} from "../appearance/InterfaceArtwork";
import {CargoYardArtwork} from "./CargoYardArtwork";

type Props={metrics:ReactNode;assets:ReactNode;blueprints:ReactNode;events:ReactElement};

// All interfaces render the same data/actions and stable arrangement IDs.
export function OverviewLayout({metrics,assets,blueprints,events}:Props){
 const style=useInterfaceStyle(),command=style==="command_desk"||style==="dark_mode";
 return <>
  <InterfaceArtwork/>
  {command&&<header className="command-desk-intro"><div><p className="command-kicker">YOUR PEOPLE. YOUR STOCK. YOUR NEXT MOVE.</p><h3>A little order<br/><em>in the void.</em></h3><p>The hangar ledger, the blueprint library, and what comes next.</p></div><CargoYardArtwork/></header>}
  <LayoutRegion region="overview">
   <div key="overview-1" data-layout-id="overview-1" data-layout-label="Overview totals" className="status-grid wide">{metrics}</div>
   <LayoutRegion key="overview-2" data-layout-id="overview-2" data-layout-label="Assets and blueprints" region="overview-inventory" className="two-column">
    <section key="recent-assets" data-layout-id="recent-assets" data-layout-label="Recent Assets" className="panel">{command&&<p className="command-kicker">01 / INVENTORY</p>}<h3>Recent Assets</h3>{assets}</section>
    <section key="blueprint-library" data-layout-id="blueprint-library" data-layout-label="Blueprint Library" className="panel">{command&&<p className="command-kicker">02 / INDUSTRY</p>}<h3>Blueprint Library</h3>{blueprints}</section>
   </LayoutRegion>
   <div key="overview-3" data-layout-id="overview-3" data-layout-label="Upcoming Events Widget" className="overview-events-slot">{events}</div>
   <SupportCard key="overview-support"/>
  </LayoutRegion>
 </>;
}
