import type {ReactNode} from "react";

export function AssetFilterDisclosure({compact,active,children}:{compact:boolean;active:boolean;children:ReactNode}){
 if(!compact)return <>{children}</>;
 return <details className="overview-filter-disclosure"><summary>Refine recent assets{active&&<span> · filters active</span>}</summary><div>{children}</div></details>;
}
