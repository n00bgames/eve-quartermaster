export type Hull={type_id:number;name:string;class_name:string;curated:boolean};
export type Source={title:string;url:string};
export type Weapon={key:string;name:string;cue:string;behavior:string;pair:string};
export type Catalog={reviewed_at:string;sources:Record<string,Source>;weapons:Weapon[];starters:Hull[];curated_hulls:number;limits:string};
export type CounterTool={name:string;examples:string[];condition:string;plan:string};
export type Variant={key:string;name:string;weapons:string[];range_note:string;tank:string;damage:string;tags:string[];confirm:string[];counter_tools:CounterTool[];plan:string;source:Source;reviewed_at:string};
export type Card=Hull&{layers:{name:string;resists:Record<string,number|null>;weakest:string[]}[];variants:Variant[];resist_note:string;fact_source:Source;context:string};
export type Composition={ships:{type_id:number|null;type_name:string;count:number;observed:number;manual:number}[];total:number;covered:number;possible_roles:{name:string;count:number}[];unresolved:number;ignored:{line:number;reason:string}[];note:string};
