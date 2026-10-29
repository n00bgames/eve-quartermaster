import {useRef,useState,type ReactNode} from "react";
// Pointer capture supports mouse, pen and touch. Only the handle suppresses scrolling.
export function DragHandle({children,label,attribute,onDrop,disabled=false}:{children:ReactNode;label:string;attribute:string;onDrop:(target:string)=>void;disabled?:boolean}){
 const start=useRef<{x:number;y:number}|null>(null),[dragging,setDragging]=useState(false);
 return <button type="button" className={`drag-grip${dragging?" dragging":""}`} disabled={disabled} aria-label={label}
 onPointerDown={e=>{if(e.button!==0)return;start.current={x:e.clientX,y:e.clientY};e.currentTarget.setPointerCapture(e.pointerId);}}
 onPointerMove={e=>{if(start.current&&Math.hypot(e.clientX-start.current.x,e.clientY-start.current.y)>5)setDragging(true);}}
 onPointerCancel={()=>{start.current=null;setDragging(false);}}
 onPointerUp={e=>{const origin=start.current;start.current=null;setDragging(false);if(!origin||Math.hypot(e.clientX-origin.x,e.clientY-origin.y)<=5)return;
 const target=document.elementFromPoint(e.clientX,e.clientY)?.closest(`[${attribute}]`);const value=target?.getAttribute(attribute);if(value)onDrop(value);
 }}> {children}</button>;
}
