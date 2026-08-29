use std::collections::{BTreeMap, BTreeSet, HashMap, VecDeque};

use chrono::{DateTime, NaiveDateTime};
use serde::Deserialize;
use serde_json::{json, Value};

pub const INPUT_SCHEMA: &str = "eqm.battle-report-input.v1";
pub const OUTPUT_SCHEMA: &str = "eqm.battle-report-output.v1";

#[derive(Debug, Clone, Deserialize)]
pub struct BattleReportInput {
    pub schema_version: String,
    pub selected_character_id: i64,
    pub seed_killmail_id: i64,
    pub gap_minutes: i64,
    #[serde(default)]
    pub side_overrides: Vec<SideOverride>,
    #[serde(default)]
    pub organization_overrides: Vec<OrganizationOverride>,
    pub rows: Vec<KillmailInput>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct SideOverride {
    pub character_id: i64,
    pub side: u8,
}

#[derive(Debug, Clone, Deserialize)]
pub struct OrganizationOverride {
    pub organization_type: String,
    pub organization_id: i64,
    pub side: u8,
}

#[derive(Debug, Clone, Deserialize)]
pub struct SystemInput {
    pub system_id: i64,
    pub system_name: String,
    pub security_status: Option<f64>,
    pub region_name: Option<String>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ShipInput {
    pub type_id: i64,
    pub type_name: String,
    pub ship_group_id: Option<i64>,
    pub ship_group_name: Option<String>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct IdentityInput {
    pub character_id: Option<i64>,
    pub character_name: Option<String>,
    pub corporation_id: Option<i64>,
    pub corporation_name: Option<String>,
    pub alliance_id: Option<i64>,
    pub alliance_name: Option<String>,
    pub faction_id: Option<i64>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct AttackerInput {
    #[serde(flatten)]
    pub identity: IdentityInput,
    pub ship: Option<ShipInput>,
    pub damage_done: i64,
    pub final_blow: bool,
}

#[derive(Debug, Clone, Deserialize)]
pub struct KillmailInput {
    pub killmail_id: i64,
    pub killmail_time: String,
    pub system: SystemInput,
    #[serde(flatten)]
    pub victim: IdentityInput,
    pub victim_name: String,
    pub timeline_victim_corporation_name: Option<String>,
    pub timeline_victim_alliance_name: Option<String>,
    pub victim_ship: Option<ShipInput>,
    pub damage_taken: i64,
    pub estimated_total_value: Option<f64>,
    pub zkill_url: String,
    #[serde(default)]
    pub attackers: Vec<AttackerInput>,
}

#[derive(Debug, Clone, Default)]
struct TeamAccumulator {
    pilot_ids: BTreeSet<i64>,
    corporation_ids: BTreeSet<i64>,
    alliance_ids: BTreeSet<i64>,
    ships_lost: i64,
    isk_lost: f64,
    unknown_value_losses: i64,
    damage_inflicted: i64,
}

#[derive(Debug, Clone)]
struct ParticipantAccumulator {
    character_id: i64,
    character_name: String,
    corporation_id: Option<i64>,
    corporation_name: Option<String>,
    alliance_id: Option<i64>,
    alliance_name: Option<String>,
    side: u8,
    ship_type_ids: BTreeSet<i64>,
    damage_done: i64,
    damage_taken: i64,
    killmail_participations: i64,
    final_blows: i64,
    losses: i64,
    loss_value: f64,
}

#[derive(Debug, Clone, Default)]
struct CompositionAccumulator {
    pilot_ids: BTreeSet<i64>,
    involved: i64,
    lost: i64,
    loss_value: f64,
}

fn affiliation(identity: &IdentityInput) -> Option<String> {
    identity
        .alliance_id
        .map(|value| format!("alliance:{value}"))
        .or_else(|| {
            identity
                .corporation_id
                .map(|value| format!("corporation:{value}"))
        })
        .or_else(|| identity.faction_id.map(|value| format!("faction:{value}")))
        .or_else(|| {
            identity
                .character_id
                .map(|value| format!("character:{value}"))
        })
}

fn aliases(identity: &IdentityInput) -> BTreeSet<String> {
    let mut values = BTreeSet::new();
    if let Some(value) = identity.character_id {
        values.insert(format!("character:{value}"));
    }
    if let Some(value) = identity.corporation_id {
        values.insert(format!("corporation:{value}"));
    }
    if let Some(value) = identity.alliance_id {
        values.insert(format!("alliance:{value}"));
    }
    if identity.corporation_id.is_none() && identity.alliance_id.is_none() {
        if let Some(value) = identity.faction_id {
            values.insert(format!("faction:{value}"));
        }
    }
    values
}

fn killmail_affiliations(row: &KillmailInput) -> BTreeSet<String> {
    affiliation(&row.victim)
        .into_iter()
        .chain(
            row.attackers
                .iter()
                .filter_map(|item| affiliation(&item.identity)),
        )
        .collect()
}

fn selected_affiliation(seed: &KillmailInput, selected_character_id: i64) -> Option<String> {
    if seed.victim.character_id == Some(selected_character_id) {
        return affiliation(&seed.victim);
    }
    seed.attackers
        .iter()
        .find(|item| item.identity.character_id == Some(selected_character_id))
        .and_then(|item| affiliation(&item.identity))
}

fn connected_rows<'a>(
    rows: &'a [KillmailInput],
    seed: &KillmailInput,
    selected: Option<&str>,
) -> Vec<&'a KillmailInput> {
    let mut included = BTreeSet::from([seed.killmail_id]);
    let mut affiliations = killmail_affiliations(seed);
    if let Some(value) = selected {
        affiliations.insert(value.to_string());
    }
    loop {
        let mut changed = false;
        for row in rows {
            if included.contains(&row.killmail_id) {
                continue;
            }
            let row_affiliations = killmail_affiliations(row);
            if !affiliations.is_disjoint(&row_affiliations) {
                included.insert(row.killmail_id);
                affiliations.extend(row_affiliations);
                changed = true;
            }
        }
        if !changed {
            break;
        }
    }
    rows.iter()
        .filter(|row| included.contains(&row.killmail_id))
        .collect()
}

fn add_edge(edges: &mut BTreeMap<String, BTreeSet<String>>, left: &str, right: &str) {
    edges
        .entry(left.to_string())
        .or_default()
        .insert(right.to_string());
    edges
        .entry(right.to_string())
        .or_default()
        .insert(left.to_string());
}

fn side_map(rows: &[&KillmailInput], selected: Option<&str>) -> HashMap<String, u8> {
    let mut same_edges: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    let mut opposite_edges: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    let mut nodes = BTreeSet::new();
    for row in rows {
        let victim = affiliation(&row.victim);
        let victim_aliases = aliases(&row.victim);
        let attacker_aliases = row
            .attackers
            .iter()
            .map(|item| (&item.identity, aliases(&item.identity)))
            .collect::<Vec<_>>();
        for identity_aliases in std::iter::once(&victim_aliases)
            .chain(attacker_aliases.iter().map(|(_, values)| values))
        {
            nodes.extend(identity_aliases.iter().cloned());
            if let Some(leader) = identity_aliases.iter().next() {
                for alias in identity_aliases.iter().skip(1) {
                    add_edge(&mut same_edges, leader, alias);
                }
            }
        }
        let attackers = attacker_aliases
            .iter()
            .filter(|(_, values)| values.is_disjoint(&victim_aliases))
            .filter_map(|(identity, _)| affiliation(identity))
            .collect::<BTreeSet<_>>();
        if let Some(value) = &victim {
            nodes.insert(value.clone());
        }
        nodes.extend(attackers.iter().cloned());
        if let Some(leader) = attackers.iter().next() {
            for attacker in attackers.iter().skip(1) {
                add_edge(&mut same_edges, leader, attacker);
            }
            if let Some(victim) = &victim {
                for attacker in &attackers {
                    add_edge(&mut opposite_edges, attacker, victim);
                }
            }
        }
    }
    let selected = selected
        .map(str::to_string)
        .or_else(|| nodes.iter().next().cloned());
    let mut assigned = HashMap::new();
    let mut conflicted = BTreeSet::new();
    if let Some(selected) = &selected {
        assigned.insert(selected.clone(), 0_u8);
        let mut queue = VecDeque::from([selected.clone()]);
        while let Some(current) = queue.pop_front() {
            let current_side = assigned[&current];
            for neighbor in same_edges.get(&current).into_iter().flatten() {
                if let Some(existing) = assigned.get(neighbor) {
                    if *existing != current_side {
                        conflicted.insert(current.clone());
                        conflicted.insert(neighbor.clone());
                    }
                } else {
                    assigned.insert(neighbor.clone(), current_side);
                    queue.push_back(neighbor.clone());
                }
            }
            for neighbor in opposite_edges.get(&current).into_iter().flatten() {
                let proposed = 1 - current_side;
                if let Some(existing) = assigned.get(neighbor) {
                    if *existing != proposed {
                        conflicted.insert(current.clone());
                        conflicted.insert(neighbor.clone());
                    }
                } else {
                    assigned.insert(neighbor.clone(), proposed);
                    queue.push_back(neighbor.clone());
                }
            }
        }
    }
    for node in nodes {
        if selected.as_ref() == Some(&node) {
            assigned.insert(node, 0);
        } else if !assigned.contains_key(&node) || conflicted.contains(&node) {
            assigned.insert(node, 2);
        }
    }
    assigned
}

fn classified_side(
    identity: &IdentityInput,
    selected_character_id: i64,
    sides: &HashMap<String, u8>,
    manual_sides: &HashMap<i64, u8>,
    manual_organizations: &HashMap<(String, i64), u8>,
) -> u8 {
    if identity.character_id == Some(selected_character_id) {
        return 0;
    }
    if let Some(value) = identity.character_id.and_then(|id| manual_sides.get(&id)) {
        return *value;
    }
    if let Some(value) = identity
        .corporation_id
        .and_then(|id| manual_organizations.get(&("corporation".to_string(), id)))
    {
        return *value;
    }
    if let Some(value) = identity
        .alliance_id
        .and_then(|id| manual_organizations.get(&("alliance".to_string(), id)))
    {
        return *value;
    }
    affiliation(identity)
        .and_then(|value| sides.get(&value).copied())
        .unwrap_or(2)
}

fn ship_json(ship: &ShipInput) -> Value {
    json!({
        "type_id": ship.type_id,
        "type_name": ship.type_name,
        "ship_group_id": ship.ship_group_id,
        "ship_group_name": ship.ship_group_name,
    })
}

fn timestamp_seconds(value: &str) -> Result<i64, String> {
    if let Ok(parsed) = DateTime::parse_from_rfc3339(value) {
        return Ok(parsed.timestamp());
    }
    NaiveDateTime::parse_from_str(value, "%Y-%m-%dT%H:%M:%S%.f")
        .map(|parsed| parsed.and_utc().timestamp())
        .map_err(|error| format!("invalid Battle Report time {value:?}: {error}"))
}

fn participant_mut<'a>(
    participants: &'a mut HashMap<i64, ParticipantAccumulator>,
    participant_order: &mut Vec<i64>,
    identity: &IdentityInput,
    side: u8,
) -> Option<&'a mut ParticipantAccumulator> {
    let character_id = identity.character_id?;
    if !participants.contains_key(&character_id) {
        participant_order.push(character_id);
        participants.insert(
            character_id,
            ParticipantAccumulator {
                character_id,
                character_name: identity
                    .character_name
                    .clone()
                    .unwrap_or_else(|| format!("Character {character_id}")),
                corporation_id: identity.corporation_id,
                corporation_name: identity.corporation_name.clone(),
                alliance_id: identity.alliance_id,
                alliance_name: identity.alliance_name.clone(),
                side,
                ship_type_ids: BTreeSet::new(),
                damage_done: 0,
                damage_taken: 0,
                killmail_participations: 0,
                final_blows: 0,
                losses: 0,
                loss_value: 0.0,
            },
        );
    }
    let participant = participants
        .get_mut(&character_id)
        .expect("participant inserted");
    if participant.side != side {
        participant.side = 2;
    }
    Some(participant)
}

pub fn evaluate_battle_report(input: BattleReportInput) -> Result<Value, String> {
    if input.schema_version != INPUT_SCHEMA {
        return Err(format!(
            "unsupported Battle Report schema: {}",
            input.schema_version
        ));
    }
    if !(5..=60).contains(&input.gap_minutes) {
        return Err("Battle Report gap must be between 5 and 60 minutes".to_string());
    }
    if input.rows.is_empty() {
        return Err("Battle Report candidates cannot be empty".to_string());
    }
    if input.side_overrides.iter().any(|row| row.side > 2)
        || input.organization_overrides.iter().any(|row| row.side > 2)
    {
        return Err("Battle Report side must be 0, 1, or 2".to_string());
    }
    let seed = input
        .rows
        .iter()
        .find(|row| row.killmail_id == input.seed_killmail_id)
        .ok_or_else(|| "Battle Report seed is not present in candidates".to_string())?;
    let selected = selected_affiliation(seed, input.selected_character_id);
    let rows = connected_rows(&input.rows, seed, selected.as_deref());
    let sides = side_map(&rows, selected.as_deref());
    let manual_sides = input
        .side_overrides
        .iter()
        .filter(|row| row.character_id != input.selected_character_id && row.side <= 2)
        .map(|row| (row.character_id, row.side))
        .collect::<HashMap<_, _>>();
    let manual_organizations = input
        .organization_overrides
        .iter()
        .filter(|row| {
            matches!(row.organization_type.as_str(), "alliance" | "corporation")
                && row.organization_id > 0
                && row.side <= 2
        })
        .map(|row| {
            (
                (row.organization_type.clone(), row.organization_id),
                row.side,
            )
        })
        .collect::<HashMap<_, _>>();

    let mut teams = [
        TeamAccumulator::default(),
        TeamAccumulator::default(),
        TeamAccumulator::default(),
    ];
    let mut participants: HashMap<i64, ParticipantAccumulator> = HashMap::new();
    let mut participant_order = Vec::new();
    let mut composition: BTreeMap<(u8, i64), CompositionAccumulator> = BTreeMap::new();
    let mut timeline = Vec::new();
    let mut total_value = 0.0_f64;
    let mut unknown_values = 0_i64;

    for row in &rows {
        if let Some(value) = row.estimated_total_value {
            total_value += value;
        } else {
            unknown_values += 1;
        }
        let victim_side = classified_side(
            &row.victim,
            input.selected_character_id,
            &sides,
            &manual_sides,
            &manual_organizations,
        );
        teams[victim_side as usize].ships_lost += 1;
        if let Some(value) = row.estimated_total_value {
            teams[victim_side as usize].isk_lost += value;
        } else {
            teams[victim_side as usize].unknown_value_losses += 1;
        }
        if let Some(victim) = participant_mut(
            &mut participants,
            &mut participant_order,
            &row.victim,
            victim_side,
        ) {
            victim.losses += 1;
            victim.damage_taken += row.damage_taken.max(0);
            victim.loss_value += row.estimated_total_value.unwrap_or(0.0);
            if let Some(ship) = &row.victim_ship {
                victim.ship_type_ids.insert(ship.type_id);
                let item = composition.entry((victim_side, ship.type_id)).or_default();
                item.pilot_ids.insert(victim.character_id);
                item.involved += 1;
                item.lost += 1;
                item.loss_value += row.estimated_total_value.unwrap_or(0.0);
            }
        }
        for attacker in &row.attackers {
            let attacker_side = classified_side(
                &attacker.identity,
                input.selected_character_id,
                &sides,
                &manual_sides,
                &manual_organizations,
            );
            teams[attacker_side as usize].damage_inflicted += attacker.damage_done.max(0);
            if let Some(actor) = participant_mut(
                &mut participants,
                &mut participant_order,
                &attacker.identity,
                attacker_side,
            ) {
                actor.damage_done += attacker.damage_done.max(0);
                actor.killmail_participations += 1;
                actor.final_blows += i64::from(attacker.final_blow);
                if let Some(ship) = &attacker.ship {
                    actor.ship_type_ids.insert(ship.type_id);
                    let item = composition
                        .entry((attacker_side, ship.type_id))
                        .or_default();
                    item.pilot_ids.insert(actor.character_id);
                    item.involved += 1;
                }
            }
        }
        timeline.push(json!({
            "killmail_id": row.killmail_id,
            "killmail_time": row.killmail_time,
            "system_id": row.system.system_id,
            "system_name": row.system.system_name,
            "victim_name": row.victim_name,
            "victim_character_id": row.victim.character_id,
            "victim_corporation_id": row.victim.corporation_id,
            "victim_corporation_name": row.timeline_victim_corporation_name,
            "victim_alliance_id": row.victim.alliance_id,
            "victim_alliance_name": row.timeline_victim_alliance_name,
            "victim_ship_type_id": row.victim_ship.as_ref().map(|ship| ship.type_id),
            "victim_ship_type_name": row.victim_ship.as_ref().map(|ship| ship.type_name.clone()).unwrap_or_else(|| "Unknown hull".to_string()),
            "victim_side": victim_side,
            "damage_taken": row.damage_taken,
            "estimated_total_value": row.estimated_total_value,
            "attacker_count": row.attackers.len(),
            "zkill_url": row.zkill_url,
        }));
    }

    let ships = input
        .rows
        .iter()
        .flat_map(|row| {
            std::iter::once(row.victim_ship.as_ref())
                .chain(row.attackers.iter().map(|item| item.ship.as_ref()))
        })
        .flatten()
        .map(|ship| (ship.type_id, ship))
        .collect::<HashMap<_, _>>();
    for character_id in &participant_order {
        let participant = participants.get(character_id).expect("participant exists");
        let team = &mut teams[participant.side as usize];
        team.pilot_ids.insert(participant.character_id);
        if let Some(value) = participant.corporation_id {
            team.corporation_ids.insert(value);
        }
        if let Some(value) = participant.alliance_id {
            team.alliance_ids.insert(value);
        }
    }

    let mut organization_rows: [Vec<(String, i64, String, i64, usize)>; 3] =
        std::array::from_fn(|_| Vec::new());
    let mut organization_positions: HashMap<(u8, String, i64), usize> = HashMap::new();
    for (order, character_id) in participant_order.iter().enumerate() {
        let participant = participants.get(character_id).expect("participant exists");
        let organization = participant
            .alliance_id
            .map(|id| {
                (
                    "alliance".to_string(),
                    id,
                    participant
                        .alliance_name
                        .clone()
                        .unwrap_or_else(|| format!("Alliance {id}")),
                )
            })
            .or_else(|| {
                participant.corporation_id.map(|id| {
                    (
                        "corporation".to_string(),
                        id,
                        participant
                            .corporation_name
                            .clone()
                            .unwrap_or_else(|| format!("Corporation {id}")),
                    )
                })
            });
        if let Some((kind, id, name)) = organization {
            let key = (participant.side, kind.clone(), id);
            if let Some(position) = organization_positions.get(&key).copied() {
                organization_rows[participant.side as usize][position].3 += 1;
            } else {
                let position = organization_rows[participant.side as usize].len();
                organization_positions.insert(key, position);
                organization_rows[participant.side as usize].push((kind, id, name, 1, order));
            }
        }
    }
    for rows in &mut organization_rows {
        rows.sort_by(|left, right| right.3.cmp(&left.3).then_with(|| left.4.cmp(&right.4)));
        rows.truncate(12);
    }

    let known_total = teams.iter().map(|team| team.isk_lost).sum::<f64>();
    let mut team_payload = Vec::new();
    for side in 0..3_u8 {
        let team = &teams[side as usize];
        if side == 2 && team.pilot_ids.is_empty() && team.ships_lost == 0 {
            continue;
        }
        team_payload.push(json!({
            "side": side,
            "label": if side == 0 { "Selected pilot's side" } else if side == 1 { "Opposing side" } else { "Third parties / ambiguous" },
            "pilot_count": team.pilot_ids.len(),
            "corporation_count": team.corporation_ids.len(),
            "alliance_count": team.alliance_ids.len(),
            "ships_lost": team.ships_lost,
            "isk_lost": team.isk_lost,
            "unknown_value_losses": team.unknown_value_losses,
            "damage_inflicted": team.damage_inflicted,
            "efficiency": (known_total != 0.0).then(|| (known_total - team.isk_lost) / known_total * 100.0),
            "organizations": organization_rows[side as usize].iter().map(|(kind, id, name, count, _)| json!({
                "organization_type": kind, "organization_id": id, "name": name, "pilot_count": count,
            })).collect::<Vec<_>>(),
        }));
    }

    let mut participant_payload = participants
        .into_values()
        .map(|participant| {
            let ship_type_ids = participant.ship_type_ids.into_iter().collect::<Vec<_>>();
            json!({
                "character_id": participant.character_id,
                "character_name": participant.character_name,
                "corporation_id": participant.corporation_id,
                "corporation_name": participant.corporation_name,
                "alliance_id": participant.alliance_id,
                "alliance_name": participant.alliance_name,
                "side": participant.side,
                "ship_type_names": ship_type_ids.iter().filter_map(|id| ships.get(id).map(|ship| ship.type_name.clone())).collect::<Vec<_>>(),
                "ships": ship_type_ids.iter().filter_map(|id| ships.get(id).map(|ship| ship_json(ship))).collect::<Vec<_>>(),
                "damage_done": participant.damage_done,
                "damage_taken": participant.damage_taken,
                "killmail_participations": participant.killmail_participations,
                "final_blows": participant.final_blows,
                "losses": participant.losses,
                "loss_value": participant.loss_value,
            })
        })
        .collect::<Vec<_>>();
    participant_payload.sort_by(|left, right| {
        left["side"]
            .as_u64()
            .cmp(&right["side"].as_u64())
            .then_with(|| {
                right["damage_done"]
                    .as_i64()
                    .cmp(&left["damage_done"].as_i64())
            })
            .then_with(|| {
                left["character_name"]
                    .as_str()
                    .cmp(&right["character_name"].as_str())
            })
    });

    let mut composition_payload = composition
        .into_iter()
        .filter_map(|((side, type_id), values)| {
            ships.get(&type_id).map(|ship| {
                json!({
                    "side": side,
                    "ship_type_id": type_id,
                    "ship_type_name": ship.type_name,
                    "ship_group_id": ship.ship_group_id,
                    "ship_group_name": ship.ship_group_name,
                    "pilots": values.pilot_ids.len(),
                    "involved": values.involved,
                    "lost": values.lost,
                    "loss_value": values.loss_value,
                })
            })
        })
        .collect::<Vec<_>>();
    composition_payload.sort_by(|left, right| {
        left["side"]
            .as_u64()
            .cmp(&right["side"].as_u64())
            .then_with(|| right["involved"].as_i64().cmp(&left["involved"].as_i64()))
            .then_with(|| {
                left["ship_type_name"]
                    .as_str()
                    .cmp(&right["ship_type_name"].as_str())
            })
    });

    let connected_system_ids = rows
        .iter()
        .map(|row| row.system.system_id)
        .collect::<BTreeSet<_>>();
    let systems = input
        .rows
        .iter()
        .map(|row| (row.system.system_id, &row.system))
        .collect::<HashMap<_, _>>();
    let system_payload = connected_system_ids
        .iter()
        .filter_map(|id| {
            systems.get(id).map(|system| {
                json!({
                    "system_id": system.system_id,
                    "system_name": system.system_name,
                    "security_status": system.security_status,
                    "region_name": system.region_name,
                })
            })
        })
        .collect::<Vec<_>>();
    let regions = connected_system_ids
        .iter()
        .filter_map(|id| {
            systems
                .get(id)
                .and_then(|system| system.region_name.clone())
        })
        .collect::<BTreeSet<_>>();
    let start = rows
        .first()
        .ok_or_else(|| "Battle Report has no connected rows".to_string())?;
    let end = rows
        .last()
        .ok_or_else(|| "Battle Report has no connected rows".to_string())?;
    let start_time = timestamp_seconds(&start.killmail_time)?;
    let end_time = timestamp_seconds(&end.killmail_time)?;
    let side_overrides = manual_sides
        .iter()
        .map(|(id, side)| (id.to_string(), json!(side)))
        .collect::<serde_json::Map<_, _>>();
    let mut organization_overrides = manual_organizations
        .iter()
        .map(|((kind, id), side)| (kind.clone(), *id, *side))
        .collect::<Vec<_>>();
    organization_overrides
        .sort_by(|left, right| left.0.cmp(&right.0).then_with(|| left.1.cmp(&right.1)));

    Ok(json!({
        "schema_version": OUTPUT_SCHEMA,
        "report": {
            "seed_killmail_id": input.seed_killmail_id,
            "side_overrides": side_overrides,
            "organization_overrides": organization_overrides.into_iter().map(|(kind, id, side)| json!({
                "organization_type": kind, "organization_id": id, "side": side,
            })).collect::<Vec<_>>(),
            "start_time": start.killmail_time,
            "end_time": end.killmail_time,
            "duration_seconds": (end_time - start_time).max(0),
            "gap_minutes": input.gap_minutes,
            "systems": system_payload,
            "regions": regions,
            "killmail_count": rows.len(),
            "pilot_count": participant_payload.len(),
            "estimated_total_value": total_value,
            "unknown_value_killmails": unknown_values,
            "teams": team_payload,
            "participants": participant_payload,
            "timeline": timeline,
            "composition": composition_payload,
        }
    }))
}
