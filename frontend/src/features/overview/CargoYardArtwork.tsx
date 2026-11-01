import {useId} from "react";

/** Original EQM illustration. Decorative, not a location or live status graphic. */
export function CargoYardArtwork(){
 const id=useId(),grid=`yard-grid-${id}`,hull=`yard-hull-${id}`;
 return <figure className="command-yard" aria-hidden="true"><svg viewBox="0 0 600 350" focusable="false"><defs><pattern id={grid} width="40" height="40" patternUnits="userSpaceOnUse"><path d="M40 0H0V40" fill="none" stroke="currentColor" strokeWidth=".4"/></pattern><linearGradient id={hull} x2="0" y2="1"><stop stopColor="currentColor" stopOpacity=".18"/><stop offset="1" stopColor="currentColor" stopOpacity=".03"/></linearGradient></defs>
 <g opacity=".25"><path d="M35 40H560V310H35Z" fill={`url(#${grid})`}/><ellipse cx="320" cy="178" rx="210" ry="104" fill="none" stroke="currentColor" strokeDasharray="2 7"/><path d="M30 178H570M320 15V335" stroke="currentColor" strokeWidth=".7"/></g>
 <g transform="translate(65 10)"><path d="M160 117 299 64 455 126 317 187Z" fill={`url(#${hull})`}/><path d="m160 117 157 70v65l-157-70zm157 70 138-61v65l-138 61z" fill={`url(#${hull})`}/><g fill="none" stroke="currentColor" strokeWidth="1.2"><path d="m160 117 139-53 156 62v65l-138 61-157-70zm0 0 157 70 138-61m-138 61v65M299 64v62l-139 56m139-56 156 65"/><path d="m195 104 156 69m-121-82 156 67m-122-80 156 67M195 134v60m35-44v60m35-44v60m91-56v64m35-79v64m35-80v65"/><path d="m180 139 31 14v21l-31-14zm69 31 31 14v21l-31-14zm88 22 29-13v21l-29 13zm64-29 29-13v21l-29 13z"/><path d="m284 59 15-6 15 6m-167 54-15 6v18m323-24 14 7v18M304 264l13 6 14-6" strokeWidth="2.5"/><path d="M165 200 112 225H55m353-108 45-37h50M320 265v29h95" strokeWidth=".7"/></g></g>
 <path d="M26 28h20m-20 0v20M574 28h-20m20 0v20M26 322h20m-20 0v-20M574 322h-20m20 0v-20" fill="none" stroke="currentColor"/>
 </svg><figcaption>EQM / THE QUARTERMASTER’S DESK</figcaption></figure>;
}
