import type { CharacterSkillProfile, SkillRecord } from "../../types/skills";

const wholeNumber = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

export function groupSkillsByCategory(skills: SkillRecord[]) {
  const groups = new Map<string, SkillRecord[]>();
  for (const skill of skills) {
    const category = skill.skill_group_name || skill.skill_category_name || "Uncategorized";
    groups.set(category, [...(groups.get(category) ?? []), skill]);
  }
  return [...groups.entries()]
    .sort(([left], [right]) => left.localeCompare(right, undefined, { numeric: true, sensitivity: "base" }))
    .map(([category, rows]) => [
      category,
      [...rows].sort((left, right) => left.skill_name.localeCompare(right.skill_name, undefined, { numeric: true, sensitivity: "base" })),
    ] as const);
}

export function skillCategoryPoints(skills: SkillRecord[]) {
  return skills.reduce((total, skill) => total + skill.skillpoints_in_skill, 0);
}

export function characterSkillReport(profile: CharacterSkillProfile, generatedAt = new Date()) {
  const lines = [
    "# EVE Quartermaster Character Skill Report",
    "",
    `Character: ${profile.character_name}`,
    `Total skill points: ${wholeNumber.format(profile.total_skill_points ?? 0)}`,
    `Unallocated skill points: ${wholeNumber.format(profile.unallocated_skill_points ?? 0)}`,
    `Trained skills: ${wholeNumber.format(profile.skill_count)}`,
    `Skills synced: ${profile.skills_synced_at ? new Date(profile.skills_synced_at).toISOString() : "Never"}`,
    `Report generated: ${generatedAt.toISOString()}`,
    "",
    "## Trained Skills by Category",
  ];

  const groups = groupSkillsByCategory(profile.skills);
  for (const [category, skills] of groups) {
    lines.push(
      "",
      `### ${category}`,
      `${wholeNumber.format(skills.length)} skills | ${wholeNumber.format(skillCategoryPoints(skills))} SP`,
    );
    for (const skill of skills) {
      const activeSuffix = skill.active_skill_level !== skill.trained_skill_level
        ? ` | Active level ${skill.active_skill_level}`
        : "";
      lines.push(
        `- ${skill.skill_name} | Level ${skill.trained_skill_level}${activeSuffix} | ${wholeNumber.format(skill.skillpoints_in_skill)} SP`,
      );
    }
  }

  if (groups.length === 0) lines.push("", "No trained skills imported.");

  lines.push("", "## Current Skill Queue");
  const queue = [...profile.queue].sort((left, right) => left.queue_position - right.queue_position);
  if (queue.length === 0) {
    lines.push("", "No active skill queue.");
  } else {
    for (const entry of queue) {
      const finish = entry.finish_date ? ` | Finishes ${new Date(entry.finish_date).toISOString()}` : "";
      lines.push(`- ${entry.queue_position + 1}. ${entry.skill_name} | Training to level ${entry.finished_level}${finish}`);
    }
  }

  return `${lines.join("\n")}\n`;
}

export function characterSkillReportFilename(profile: CharacterSkillProfile) {
  const safeName = profile.character_name
    .trim()
    .replace(/[^a-z0-9]+/gi, "-")
    .replace(/^-+|-+$/g, "")
    .toLowerCase() || "character";
  return `${safeName}-eqm-skills.txt`;
}
