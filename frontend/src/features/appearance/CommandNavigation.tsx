import {useId,useState,type ReactNode} from "react";
import {isSpaceInterface} from "./interfaceCatalog";
import {SpaceNavigation} from "./SpaceNavigation";
import {useInterfaceStyle} from "./AppearanceProvider";

/** A compact mobile entry point; the same customizable nav remains mounted. */
export function CommandNavigation({children}:{children:ReactNode}){
 const id=useId(),[open,setOpen]=useState(false),style=useInterfaceStyle();
 if(isSpaceInterface(style))return <SpaceNavigation>{children}</SpaceNavigation>;
 if(style!=="command_desk")return <>{children}</>;
 return <div className={`command-navigation${open?" is-open":""}`}><button type="button" className="command-mobile-nav-toggle" aria-expanded={open} aria-controls={id} onClick={()=>setOpen(!open)}>{open?"Close navigation":"Open navigation"}<span aria-hidden="true">{open?"−":"+"}</span></button><div id={id} className="command-navigation-content">{children}</div></div>;
}
