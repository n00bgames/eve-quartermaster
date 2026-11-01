import {useEffect,useState} from 'react';
import {EveItemName} from '../clientLinks/EveClientLinks';
export function JourneyHull({typeId,name}:{typeId?:number|null;name?:string|null}){
 const [bad,setBad]=useState(false);
 useEffect(()=>setBad(false),[typeId]);
 return <span className="journey-hull">{typeId&&!bad?<img key={typeId} src={`https://images.evetech.net/types/${typeId}/icon?size=32`} width={28} height={28} alt="" loading="lazy" referrerPolicy="no-referrer" onError={()=>setBad(true)}/>:<span className="journey-hull-unknown" aria-hidden="true">?</span>}{typeId?<EveItemName typeId={typeId} name={name??`Type ${typeId}`}/>:<span>Unknown hull</span>}</span>;
}
