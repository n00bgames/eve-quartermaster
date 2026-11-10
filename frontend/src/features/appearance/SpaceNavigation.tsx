import {useEffect,useId,useRef,useState,type ReactNode} from "react";
import {Menu,X} from "lucide-react";
import {useInterfaceStyle} from "./AppearanceProvider";

/** Keep the real permission-filtered menu and its editor mounted in every layout. */
export function SpaceNavigation({children}:{children:ReactNode}) {
  const style=useInterfaceStyle(),id=useId(),[open,setOpen]=useState(false),toggle=useRef<HTMLButtonElement>(null);
  useEffect(()=>setOpen(false),[style]);
  return <div className={`space-navigation${open?" is-open":""}`} onKeyDown={event=>{
    if(event.key==="Escape"&&open){setOpen(false);event.currentTarget.querySelector<HTMLButtonElement>(".space-menu-toggle")?.focus();}
  }}>
    <button ref={toggle} type="button" className="space-menu-toggle" aria-expanded={open} aria-controls={id} onClick={()=>setOpen(!open)}>{open?<X size={20}/>:<Menu size={20}/>}<span>{open?"Close menu":"Menu"}</span></button>
    <div id={id} className="space-navigation-content" onClick={event=>{
      if(event.target instanceof Element && event.target.closest(".nav-module > button")){setOpen(false);if(toggle.current?.getClientRects().length)toggle.current.focus();}
    }}>{children}</div>
  </div>;
}
