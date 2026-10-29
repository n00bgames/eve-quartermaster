import {DragHandle} from "./DragHandle";
import React,{Children,cloneElement,isValidElement,type ReactNode,type ReactElement} from "react";
import {useAppearance} from "./AppearanceProvider";
import {orderedKeys,move,mergePanelOrder} from "./model";
type Props={region:string;children:ReactNode;className?:string;"data-layout-id"?:string;"data-layout-label"?:string};
export function LayoutRegion({region,children,className="stacked"}:Props){
 const a=useAppearance();const items=Children.toArray(children).filter(isValidElement) as ReactElement<Record<string,unknown>>[];
 const ids=items.map((c,i)=>String(c.props["data-layout-id"]??c.key?.replace(/[^a-zA-Z0-9_.:-]/g,"")??`panel-${i}`));const order=orderedKeys(ids,a.personal.preferences.layouts?.[region]);
 function save(next:string[]){void a.save({layouts:{...a.personal.preferences.layouts,[region]:mergePanelOrder(a.personal.preferences.layouts?.[region],next)}});}
 return <div className={className} data-layout-region={region}>{order.map((id,index)=>{const child=items[ids.indexOf(id)],label=String(child.props["data-layout-label"]??`Panel ${index+1}`);
 const controls=a.editing?<div className="layout-handle" {...{[`data-drop-${region}`]:id}}><DragHandle label={`Drag ${label}`} attribute={`data-drop-${region}`} disabled={a.busy} onDrop={target=>{if(order.includes(target))save(move(order,index,order.indexOf(target)));}}>⠿ {label}</DragHandle><button type="button" disabled={a.busy||index===0} aria-label={`Move ${label} up`} onClick={()=>save(move(order,index,index-1))}>↑</button><button type="button" disabled={a.busy||index===order.length-1} aria-label={`Move ${label} down`} onClick={()=>save(move(order,index,index+1))}>↓</button><button type="button" disabled={a.busy||!a.personal.preferences.layouts?.[region]} onClick={()=>{const next={...a.personal.preferences.layouts};delete next[region];void a.save({layouts:next});}}>Reset section</button></div>:null;
 if(typeof child.type==="string")return cloneElement(child,{key:id,[`data-drop-${region}`]:id,className:`${child.props.className??""}${a.editing?" layout-editable":""}`},controls,child.props.children as ReactNode);
 return <div key={id} {...{[`data-drop-${region}`]:id}} className={a.editing?"layout-component layout-editable":"layout-component"}>{controls}{child}</div>;
 })}</div>;
}
