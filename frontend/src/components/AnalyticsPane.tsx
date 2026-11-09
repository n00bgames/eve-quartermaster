import {useEffect,useRef,useState,type ReactNode} from "react";
import {ChevronRight} from "lucide-react";
import "./analyticsPane.css";

/** Closed on mount; mount expensive content only on the first expansion. */
export function AnalyticsPane({title,description,id,className="",children,unmountOnClose=false}:{
  title:string;description?:string;id?:string;className?:string;children:ReactNode;unmountOnClose?:boolean;
}) {
  const [open,setOpen]=useState(false),[visited,setVisited]=useState(false);
  const element=useRef<HTMLElement>(null);
  useEffect(()=>{
    if(!id)return;
    function matches(hash:string){try{return decodeURIComponent(hash.replace(/^#/,""))===id;}catch{return false;}}
    function activate(){setVisited(true);setOpen(true);requestAnimationFrame(()=>element.current?.scrollIntoView({block:"start"}));}
    function hash(){if(matches(window.location.hash))activate();}
    function click(event:MouseEvent){const link=(event.target as Element|null)?.closest?.('a[href^="#"]');if(link&&matches(link.getAttribute("href")??""))activate();}
    hash();window.addEventListener("hashchange",hash);document.addEventListener("click",click);
    return()=>{window.removeEventListener("hashchange",hash);document.removeEventListener("click",click);};
  },[id]);
  return <section ref={element} id={id} className={`analytics-pane ${className}`} aria-label={title}>
    <details open={open} onToggle={event=>{const next=event.currentTarget.open;setOpen(next);if(next)setVisited(true);}}>
      <summary aria-label={title} onClick={event=>{event.preventDefault();setVisited(true);setOpen(value=>!value);}}><ChevronRight size={18} aria-hidden="true"/><span><strong>{title}</strong>{description&&<small>{description}</small>}</span><small className="analytics-pane-action">{open?"Collapse":"Expand"}</small></summary>
      {(open||visited&&!unmountOnClose)&&<div className="analytics-pane-content" hidden={!open}>{children}</div>}
    </details>
  </section>;
}
