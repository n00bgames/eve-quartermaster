import type { SkillDogmaBonus, SkillDogmaBonusProfile } from "../../types/skills";

export type GroupedSkillDogmaProfile = { names: string[]; groupName: string | null; bonuses: SkillDogmaBonus[] };

const PERCENT_UNITS = new Set([105, 109, 111, 121]);

function numberText(value: number) {
  return Number.isInteger(value) ? value.toLocaleString() : value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

export function bonusValueText(bonus: SkillDogmaBonus, level = 1) {
  const value = Math.abs(bonus.value * level);
  return `${numberText(value)}${PERCENT_UNITS.has(bonus.unit_id ?? -1) ? "%" : ""}`;
}

export function groupBonusProfiles(profiles: SkillDogmaBonusProfile[]): GroupedSkillDogmaProfile[] {
  const grouped = new Map<string, GroupedSkillDogmaProfile>();
  for (const profile of profiles) {
    const signature = JSON.stringify(profile.bonuses.map((bonus) => [bonus.value, bonus.unit_id, bonus.text]));
    const current = grouped.get(signature);
    if (current) current.names.push(profile.affected_type_name);
    else grouped.set(signature, { names: [profile.affected_type_name], groupName: profile.group_name ?? null, bonuses: profile.bonuses });
  }
  return Array.from(grouped.values()).sort((left, right) => right.names.length - left.names.length || left.names[0].localeCompare(right.names[0]));
}
