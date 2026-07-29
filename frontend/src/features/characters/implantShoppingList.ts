import type { JumpCloneImplant } from "../../types/jumpClones";

export type ImplantShoppingList = {
  text: string;
  itemTypeCount: number;
  implantCount: number;
};

export function buildImplantShoppingList(implants: JumpCloneImplant[]): ImplantShoppingList {
  const quantities = new Map<string, { name: string; quantity: number }>();

  for (const implant of implants) {
    const name = implant.name.trim();
    if (!name) continue;
    const key = name.toLocaleLowerCase();
    const current = quantities.get(key);
    quantities.set(key, { name: current?.name ?? name, quantity: (current?.quantity ?? 0) + 1 });
  }

  const rows = [...quantities.values()].sort((left, right) => left.name.localeCompare(right.name));
  return {
    text: rows.map((row) => `${row.name} ${row.quantity}`).join("\n"),
    itemTypeCount: rows.length,
    implantCount: rows.reduce((total, row) => total + row.quantity, 0),
  };
}