import {useRef,type HTMLAttributes,type ReactNode} from "react";

type Props=HTMLAttributes<HTMLElement>&{dropdown:boolean;label:string;children:ReactNode};
export function NavigationGroup({dropdown,label,children,...props}:Props) {
 const ref=useRef<HTMLDetailsElement>(null);
 if(!dropdown)return <div {...props}>{children}</div>;
 return <details {...props} ref={ref} onClick={event=>{
   if(event.target instanceof Element && event.target.closest(".nav-module > button") && ref.current){ref.current.open=false;ref.current.querySelector("summary")?.focus();}
 }}><summary className="nav-group-summary">{label}</summary>{children}</details>;
}
