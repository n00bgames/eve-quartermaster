import assert from "node:assert/strict";
import test from "node:test";

import { characterSkillReport, characterSkillReportFilename, groupSkillsByCategory } from "../src/features/characters/skillReport.ts";
import type { CharacterSkillProfile, SkillRecord } from "../src/types/skills.ts";

const skills: SkillRecord[] = [
  {
    id: 1,
    skill_type_id: 101,
    skill_name: "Warp Drive Operation",
    skill_group_name: "Navigation",
    skill_category_name: "Skill",
    trained_skill_level: 5,
    active_skill_level: 5,
    skillpoints_in_skill: 256000,
  },
  {
    id: 2,
    skill_type_id: 102,
    skill_name: "Afterburner",
    skill_group_name: "Navigation",
    skill_category_name: "Skill",
    trained_skill_level: 4,
    active_skill_level: 4,
    skillpoints_in_skill: 45255,
  },
  {
    id: 3,
    skill_type_id: 103,
    skill_name: "Drones",
    skill_group_name: "Drones",
    skill_category_name: "Skill",
    trained_skill_level: 5,
    active_skill_level: 4,
    skillpoints_in_skill: 256000,
  },
];

const profile: CharacterSkillProfile = {
  token_id: 4,
  character_id: 90000001,
  character_name: "Example Pilot",
  owner_user_id: 1,
  sync_opt_out: false,
  admin_override_visible: false,
  total_skill_points: 557255,
  unallocated_skill_points: 1000,
  skills_synced_at: "2026-07-26T12:00:00Z",
  skill_queue_synced_at: "2026-07-26T12:00:00Z",
  missing_skill_scopes: [],
  skill_count: 3,
  queue_count: 1,
  skills,
  queue: [{
    id: 5,
    queue_position: 0,
    skill_type_id: 104,
    skill_name: "Evasive Maneuvering",
    finished_level: 5,
    finish_date: "2026-07-27T12:00:00Z",
  }],
};

test("groups and sorts trained skills by category and name", () => {
  const groups = groupSkillsByCategory(skills);
  assert.deepEqual(groups.map(([name]) => name), ["Drones", "Navigation"]);
  assert.deepEqual(groups[1][1].map((skill) => skill.skill_name), ["Afterburner", "Warp Drive Operation"]);
});

test("builds a deterministic shareable skill report", () => {
  const report = characterSkillReport(profile, new Date("2026-07-26T13:00:00Z"));
  assert.match(report, /Character: Example Pilot/);
  assert.match(report, /Total skill points: 557,255/);
  assert.match(report, /### Drones/);
  assert.match(report, /Drones \| Level 5 \| Active level 4 \| 256,000 SP/);
  assert.match(report, /### Navigation/);
  assert.match(report, /Afterburner \| Level 4 \| 45,255 SP/);
  assert.match(report, /Evasive Maneuvering \| Training to level 5/);
  assert.equal(characterSkillReportFilename(profile), "example-pilot-eqm-skills.txt");
});
