import type {InterfaceStyle, Theme, NavGroup} from "./model";

export const spaceInterfaces = {
  orbital_ring: {
    name: "Orbital Ring", kicker: "CAPSULE CONTROL / ORBITAL ARRAY",
    description: "A teal orbital deck with a horizontal department dock, circular instruments and capsule panels.",
    layout: "Top department dock", geometry: "Rings & capsules",
    theme: {background:"#061b24",panel:"#0b2c36",text:"#e6fcfa",muted:"#a0c8cb",accent:"#6bf0ce",border:"#37656b"},
  },
  imperial_archive: {
    name: "Imperial Archive", kicker: "IMPERIAL RECORDS / STATION ARCHIVE",
    description: "An ivory station archive with tall arched panels, engraved page emblems and a two-column index.",
    layout: "Left archive index", geometry: "Arches & seals",
    theme: {background:"#ece5d5",panel:"#fffbf1",text:"#302832",muted:"#685766",accent:"#735125",border:"#a79b86"},
  },
  void_cartography: {
    name: "Void Cartography", kicker: "DEEP FIELD / CARTOGRAPHIC ARRAY",
    description: "A violet star-chart console with a right-side navigation atlas, diamond markers and plotted panels.",
    layout: "Right navigation atlas", geometry: "Diamonds & coordinates",
    theme: {background:"#170d2b",panel:"#28183d",text:"#f4efff",muted:"#c3b1d8",accent:"#d3f57b",border:"#725d8b"},
  },
  frontier_terminal: {
    name: "Frontier Terminal", kicker: "OUTER RIM / INDUSTRIAL TERMINAL",
    description: "An industrial rust-and-bone console with a hamburger drawer, vertical dropdown sections and stamped panels.",
    layout: "Hamburger / vertical dropdowns", geometry: "Notches & stencils",
    theme: {background:"#241811",panel:"#35261e",text:"#fff1d7",muted:"#d3b99d",accent:"#ffaf78",border:"#8c6951"},
  },
} satisfies Record<string,{name:string;kicker:string;description:string;layout:string;geometry:string;theme:Theme}>;

export type SpaceInterface = keyof typeof spaceInterfaces;
export function isSpaceInterface(style: InterfaceStyle): style is SpaceInterface {
  return Object.prototype.hasOwnProperty.call(spaceInterfaces, style);
}
export function interfaceShellClass(style: InterfaceStyle): string {
  if (style === "command_desk") return " command-desk-shell";
  return isSpaceInterface(style) ? ` space-interface-shell ${style.replace(/_/g, "-")}-shell` : "";
}

/** Presentation grouping only; keep saved shortcuts/order intact for other layouts. */
export function frontierNavigationGroups(groups: NavGroup[]): NavGroup[] {
  const profile = "profile", admin = new Set(["settings", "audit"]);
  const available = new Set(groups.flatMap(group => group.modules));
  return [
    ...groups.map(group => ({...group,modules:group.modules.filter(id => id !== profile && !admin.has(id))})).filter(group => group.modules.length),
    ...(available.has(profile) ? [{id:"frontier-profile",name:"Profile",modules:[profile]}] : []),
    {id:"frontier-administration",name:"Administration",modules:[...admin].filter(id => available.has(id))},
  ].filter(group => group.modules.length);
}
