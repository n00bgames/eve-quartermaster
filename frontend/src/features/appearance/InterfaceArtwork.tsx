import {useInterfaceStyle} from "./AppearanceProvider";
import {isSpaceInterface,spaceInterfaces} from "./interfaceCatalog";
import {ModuleSigil} from "./ModuleSigil";

export function InterfacePageMark({module}:{module:string}) {
 const style=useInterfaceStyle();
 if(!isSpaceInterface(style))return null;
 return <div className="interface-page-mark"><ModuleSigil module={module} large/><span>{spaceInterfaces[style].name}<small>{module.replace(/_/g," ")}</small></span></div>;
}
/** Decorative original vector artwork; no fabricated operational telemetry. */
export function InterfaceArtwork() {
 const style=useInterfaceStyle();if(!isSpaceInterface(style))return null;
 const choice=spaceInterfaces[style];
 return <section className="interface-scene" aria-label={`${choice.name} workspace`}><div><p className="scene-kicker">{choice.kicker}</p><h3>{style==="orbital_ring"?"Your station. In orbit.":style==="imperial_archive"?"The capsuleer’s archive.":style==="void_cartography"?"Chart your next move.":"Built beyond the core."}</h3><p>People, industry and operations across New Eden.</p></div>
 <svg className="interface-artwork" viewBox="0 0 440 170" fill="none" stroke="currentColor" strokeWidth="1" aria-hidden="true">
  {style==="orbital_ring"?<><ellipse cx="230" cy="87" rx="170" ry="58" transform="rotate(-12 230 87)"/><ellipse cx="230" cy="87" rx="125" ry="42" transform="rotate(-12 230 87)"/><circle cx="230" cy="87" r="48"/><circle cx="230" cy="87" r="31"/><path d="M230 27V9m0 156v-18M163 87h-50m234 0h-50M215 67l30 20-30 20z"/><circle cx="78" cy="107" r="7" fill="currentColor"/><circle cx="360" cy="42" r="4" fill="currentColor"/></>:
   style==="imperial_archive"?<><path d="M48 150V70a40 40 0 0 1 80 0v80zm93 0V48a40 40 0 0 1 80 0v102zm93 0V70a40 40 0 0 1 80 0v80zm93 0V90a30 30 0 0 1 60 0v60z"/><path d="M30 151h374M70 91h36m-36 12h36m58-30h34m-34 12h34m58 18h36"/><circle cx="181" cy="47" r="17"/><path d="m181 33 5 9 10 5-10 4-5 10-5-10-10-4 10-5z"/></>:
   style==="void_cartography"?<><path d="M25 137 100 49l87 60 100-80 120 94M100 49l187-20M187 109l220 14M100 49v102m187-122v122M20 150h400" strokeDasharray="4 7"/>{[[25,137],[100,49],[187,109],[287,29],[407,123]].map(([x,y],i)=><g key={i}><path d={`m${x} ${y-10} 10 10-10 10-10-10z`}/><circle cx={x} cy={y} r="2" fill="currentColor"/></g>)}<circle cx="287" cy="29" r="24"/><path d="M15 15h35m-35 0v30m400 110h-35m35 0v-30"/></>:
   <><path d="M25 33h390v111H25zM25 55h390M75 55v89M168 55v89M305 55v89M25 121h390"/><path d="M35 43h28m-28 28h28m-28 12h28m-28 12h28M90 108V85l20-16 20 16v23zm93 0V75h44v33zm60 0V65h44v43zm76-31h77m-77 12h60m-60 12h45"/><path d="m40 22 8-8h78l8 8m142 0 8-8h90l8 8M35 154h63m15 0h31m10 0h103m15 0h126"/></>}
 </svg></section>;
}
