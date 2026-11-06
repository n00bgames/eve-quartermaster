export type Hull={type_id:number;name:string;class_name:string;curated:boolean};
export type Source={title:string;url:string};
export type Weapon={key:string;name:string;cue:string;behavior:string;pair:string};
export type Catalog={reviewed_at:string;sources:Record<string,Source>;weapons:Weapon[];starters:Hull[];hulls:Hull[];curated_hulls:number;limits:string};
export type CounterTool={name:string;examples:string[];condition:string;plan:string};
export type Variant={key:string;name:string;weapons:string[];range_note:string;tank:string;damage:string;tags:string[];confirm:string[];counter_tools:CounterTool[];plan:string;source:Source;reviewed_at:string};
export type Card=Hull&{layers:{name:string;resists:Record<string,number|null>;weakest:string[]}[];variants:Variant[];resist_note:string;fact_source:Source;context:string;weapon_profile:{bonused:string[];mounts:string[];effects_loaded:boolean}};
type WeaponStats = {name:string;group:string;slot_flag:string;charge_name:string|null;dps:number;optimal_m:number|null;falloff_m:number|null;range_m:number|null;control_range_m?:number|null};
export type FitExample = {
  killmail_id:number;
  killmail_time:string;
  estimated_loss_isk:number|null;
  modules:{slot:string;name:string;quantity:number;charge:string|null}[];
  weapon_families:string[];
  stats:null|{
    offense:{total_dps:number|null;volley:number|null;weapons:WeaponStats[]};
    defense:{ehp:number;shield_resists:Record<string,number>;armor_resists:Record<string,number>;structure_resists:Record<string,number>};
    mobility:{max_velocity:number|null;align_time:number|null};
    targeting:{targeting_range:number|null};
  };
  counter_fits:{hull:string;fit:string;plan:string;condition:string}[];
};
export type FitResearch = {checked_at:string;scanned_count:number;sample_count:number;observed_weapons:{name:string;count:number}[];assumptions:string;examples:FitExample[]};
export type Composition={ships:{type_id:number|null;type_name:string;count:number;observed:number;manual:number}[];total:number;covered:number;possible_roles:{name:string;count:number}[];unresolved:number;ignored:{line:number;reason:string}[];note:string};
