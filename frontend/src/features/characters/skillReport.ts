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

function sortedProfiles(profiles: CharacterSkillProfile[]) {
  return [...profiles].sort((left, right) =>
    left.character_name.localeCompare(right.character_name, undefined, { numeric: true, sensitivity: "base" })
    || left.character_id - right.character_id,
  );
}

function sortedSkills(skills: SkillRecord[]) {
  return groupSkillsByCategory(skills).flatMap(([, rows]) => rows);
}

function csvCell(value: string | number | null | undefined) {
  const text = value == null ? "" : String(value);
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export function allCharacterSkillsCsv(profiles: CharacterSkillProfile[]) {
  const columns = [
    "character_id", "character_name", "total_skill_points", "unallocated_skill_points", "skills_synced_at",
    "skill_type_id", "skill_name", "skill_group_name", "skill_category_name", "trained_skill_level",
    "active_skill_level", "skillpoints_in_skill", "skill_last_synced_at",
  ];
  const rows: (string | number | null | undefined)[][] = [];
  for (const profile of sortedProfiles(profiles)) {
    const skills = sortedSkills(profile.skills);
    if (skills.length === 0) {
      rows.push([
        profile.character_id,
        profile.character_name,
        profile.total_skill_points,
        profile.unallocated_skill_points,
        profile.skills_synced_at,
        ...Array<null>(8).fill(null),
      ]);
      continue;
    }
    for (const skill of skills) {
      rows.push([
        profile.character_id, profile.character_name, profile.total_skill_points, profile.unallocated_skill_points,
        profile.skills_synced_at, skill.skill_type_id, skill.skill_name, skill.skill_group_name,
        skill.skill_category_name, skill.trained_skill_level, skill.active_skill_level,
        skill.skillpoints_in_skill, skill.last_synced_at,
      ]);
    }
  }
  return `${[columns, ...rows].map((row) => row.map(csvCell).join(",")).join("\n")}\n`;
}

export function allCharacterSkillsJson(profiles: CharacterSkillProfile[], generatedAt = new Date()) {
  const characters = sortedProfiles(profiles).map((profile) => ({
    character_id: profile.character_id,
    character_name: profile.character_name,
    total_skill_points: profile.total_skill_points ?? null,
    unallocated_skill_points: profile.unallocated_skill_points ?? null,
    skills_synced_at: profile.skills_synced_at ?? null,
    skill_queue_synced_at: profile.skill_queue_synced_at ?? null,
    skill_count: profile.skill_count,
    queue_count: profile.queue_count,
    skills: sortedSkills(profile.skills),
    queue: [...profile.queue].sort((left, right) => left.queue_position - right.queue_position),
  }));
  return JSON.stringify({
    schema_version: 1,
    generated_at: generatedAt.toISOString(),
    character_count: characters.length,
    skill_count: characters.reduce((total, character) => total + character.skills.length, 0),
    characters,
  }, null, 2) + "\n";
}

export function allCharacterSkillsFilename(format: "csv" | "json", generatedAt = new Date()) {
  return `eve-quartermaster-skills-all-${generatedAt.toISOString().slice(0, 10)}.${format}`;
}
