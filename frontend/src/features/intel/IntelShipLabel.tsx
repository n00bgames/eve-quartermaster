import {EveItemName} from "../clientLinks/EveClientLinks";
export const unknownShipIcon="/icons/unknown-ship.png";
export function IntelShipLabel({typeId,name}:{typeId:number|null;name:string}){
 return <span className="intel-ship-label"><img width={32} height={32} loading="lazy" alt="" src={typeId?`https://images.evetech.net/types/${typeId}/icon?size=64`:unknownShipIcon} onError={e=>{if(e.currentTarget.getAttribute('src')!==unknownShipIcon)e.currentTarget.src=unknownShipIcon;}}/><span>{typeId?<EveItemName name={name} typeId={typeId}/>:name}</span></span>;
}
