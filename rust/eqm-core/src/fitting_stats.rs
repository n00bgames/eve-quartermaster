use std::collections::{BTreeMap, BTreeSet};

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::fitting_math::{
    capacitor_depletion_seconds, capacitor_stable_percent, dogma_multiplier,
    stacking_multiplier, stacking_raw_multiplier, unpenalized_multiplier,
};

const FITTED_SLOTS: [&str; 6] = [
    "HiSlot",
    "MedSlot",
    "LoSlot",
    "RigSlot",
    "SubSystemSlot",
    "ServiceSlot",
];
const BAY_SLOTS: [&str; 16] = [
    "Cargo",
    "DroneBay",
    "FighterBay",
    "FuelBay",
    "FleetHangar",
    "ShipMaintenanceBay",
    "FleetMaintenanceBay",
    "InfrastructureBay",
    "OreHold",
    "MineralHold",
    "GasHold",
    "IceHold",
    "AmmoHold",
    "PlanetaryCommoditiesHold",
    "CommandCenterHold",
    "QuafeHold",
];

const SHIELD_MANAGEMENT_TYPE_ID: i64 = 3416;
const MECHANICS_TYPE_ID: i64 = 3392;
const HULL_UPGRADES_TYPE_ID: i64 = 3394;
const NAVIGATION_TYPE_ID: i64 = 3449;
const CAPACITOR_SYSTEMS_OPERATION_TYPE_ID: i64 = 3417;
const CAPACITOR_MANAGEMENT_TYPE_ID: i64 = 3418;
const WARHEAD_UPGRADES_TYPE_ID: i64 = 20315;
const RAPID_LAUNCH_TYPE_ID: i64 = 21071;
const SPACESHIP_COMMAND_TYPE_ID: i64 = 3327;
const EVASIVE_MANEUVERING_TYPE_ID: i64 = 3453;
const ADVANCED_SPACESHIP_COMMAND_TYPE_ID: i64 = 20342;

#[derive(Clone, Debug, Deserialize)]
pub struct FittingStatsInput {
    pub schema_version: String,
    pub ship_type_id: i64,
    #[serde(default)]
    pub ship_attrs: BTreeMap<String, f64>,
    #[serde(default)]
    pub items: Vec<FittingStatsItem>,
    #[serde(default)]
    pub dogma: BTreeMap<i64, BTreeMap<String, f64>>,
    #[serde(default)]
    pub dogma_effects: BTreeMap<i64, Vec<Value>>,
    #[serde(default)]
    pub names: BTreeMap<i64, String>,
    #[serde(default)]
    pub group_names: BTreeMap<i64, String>,
    #[serde(default)]
    pub group_ids: BTreeMap<i64, i64>,
    #[serde(default)]
    pub skill_levels: BTreeMap<i64, i64>,
    #[serde(default)]
    pub skill_name_levels: BTreeMap<String, i64>,
    #[serde(default)]
    pub volumes: BTreeMap<i64, f64>,
    pub ship_capacity: Option<f64>,
    pub ship_mass: Option<f64>,
    #[serde(default)]
    pub implant_type_ids: BTreeSet<i64>,
    #[serde(default)]
    pub stats_item_ids: BTreeSet<i64>,
    #[serde(default)]
    pub heat: bool,
}

#[derive(Clone, Debug, Deserialize)]
pub struct FittingStatsItem {
    pub id: i64,
    pub type_id: i64,
    pub charge_type_id: Option<i64>,
    pub flag: String,
    #[serde(default = "default_quantity")]
    pub quantity: i64,
    #[serde(default = "default_state")]
    pub simulation_state: String,
}

fn default_quantity() -> i64 {
    1
}

fn default_state() -> String {
    "online".to_string()
}

#[derive(Clone, Debug, Serialize)]
pub struct FittingStatsOutput {
    pub schema_version: &'static str,
    pub offense: OffenseStats,
    pub defense: DefenseStats,
    pub mobility: MobilityStats,
    pub capacitor: CapacitorStats,
    pub cargo_bays: Vec<CargoBayStats>,
    pub targeting: TargetingStats,
    pub notes: Vec<String>,
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct DamageProfile {
    pub em: f64,
    pub thermal: f64,
    pub kinetic: f64,
    pub explosive: f64,
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct OffenseStats {
    pub turret_dps: f64,
    pub launcher_dps: f64,
    pub drone_dps: f64,
    pub total_dps: f64,
    pub volley: f64,
    pub damage_types: DamageProfile,
    pub weapon_count: usize,
    pub max_range_m: Option<f64>,
    pub weapons: Vec<Value>,
}

#[derive(Clone, Debug, Serialize)]
pub struct DefenseStats {
    pub shield_hp: f64,
    pub armor_hp: f64,
    pub structure_hp: f64,
    pub ehp: f64,
    pub shield_ehp: f64,
    pub armor_ehp: f64,
    pub structure_ehp: f64,
    pub shield_resists: DamageProfile,
    pub armor_resists: DamageProfile,
    pub structure_resists: DamageProfile,
    pub shield_peak_recharge: Option<f64>,
    pub active_tank_hps: f64,
    pub shield_repair_hps: f64,
    pub armor_repair_hps: f64,
    pub structure_repair_hps: f64,
}

#[derive(Clone, Debug, Serialize)]
pub struct MobilityStats {
    pub max_velocity: Option<f64>,
    pub warp_speed: Option<f64>,
    pub align_time: Option<f64>,
    pub signature_radius: Option<f64>,
    pub mass: Option<f64>,
    pub implant_modifiers_applied: usize,
}

#[derive(Clone, Debug, Serialize)]
pub struct CapacitorStats {
    pub capacity: Option<f64>,
    pub recharge_time: Option<f64>,
    pub peak_recharge: Option<f64>,
    pub draw_per_second: f64,
    pub stable: bool,
    pub stable_percent: Option<f64>,
    pub depletion_seconds: Option<f64>,
    pub modules: Vec<Value>,
}

#[derive(Clone, Debug, Serialize)]
pub struct CargoBayStats {
    pub key: &'static str,
    pub label: &'static str,
    pub used: f64,
    pub capacity: Option<f64>,
    pub ok: bool,
    pub percent: Option<f64>,
}

#[derive(Clone, Debug, Serialize)]
pub struct TargetingStats {
    pub max_targets: Option<f64>,
    pub targeting_range: Option<f64>,
    pub scan_resolution: Option<f64>,
    pub sensor_strength: Option<f64>,
    pub drone_control_range_m: Option<f64>,
}

fn normalize_attr(name: &str) -> String {
    name.to_lowercase()
        .chars()
        .filter(|character| character.is_ascii_alphanumeric())
        .collect()
}

fn normalized_attrs(attrs: &BTreeMap<String, f64>) -> BTreeMap<String, f64> {
    attrs
        .iter()
        .map(|(name, value)| (normalize_attr(name), *value))
        .collect()
}

fn attr_value(attrs: &BTreeMap<String, f64>, names: &[&str]) -> Option<f64> {
    names
        .iter()
        .find_map(|name| attrs.get(&normalize_attr(name)).copied())
}

fn slot_prefix(flag: &str) -> &'static str {
    for prefix in FITTED_SLOTS.into_iter().chain(BAY_SLOTS) {
        if flag.starts_with(prefix) {
            return prefix;
        }
    }
    if flag.to_lowercase().contains("cargo") {
        "Cargo"
    } else {
        "Other"
    }
}

fn module_quantity(item: &FittingStatsItem) -> i64 {
    if FITTED_SLOTS.contains(&slot_prefix(&item.flag)) {
        1
    } else {
        item.quantity.max(1)
    }
}

fn item_is_online(item: &FittingStatsItem) -> bool {
    item.simulation_state.to_lowercase() != "offline"
}

fn item_is_running(item: &FittingStatsItem) -> bool {
    matches!(
        item.simulation_state.to_lowercase().as_str(),
        "active" | "overheated"
    )
}

fn item_is_overheated(item: &FittingStatsItem, heat: bool) -> bool {
    heat && item.simulation_state.eq_ignore_ascii_case("overheated")
}

fn cycle_seconds(attrs: &BTreeMap<String, f64>) -> Option<f64> {
    attr_value(attrs, &["duration", "speed", "rateOfFire"])
        .filter(|value| *value > 0.0)
        .map(|value| value / 1000.0)
}

fn module_is_passive(
    item: &FittingStatsItem,
    attrs: &BTreeMap<String, f64>,
    group: &str,
    name: &str,
) -> bool {
    if matches!(slot_prefix(&item.flag), "RigSlot" | "SubSystemSlot") {
        return true;
    }
    let family = format!("{name} {group}").to_lowercase();
    let active_words = [
        "launcher", "turret", "smartbomb", "bomb launcher", "bastion", "siege",
        "triage", "industrial core", "shield booster", "armor repair", "hull repair",
        "capacitor booster", "afterburner", "microwarpdrive", "micro jump",
        "target painter", "webifier", "warp disrupt", "warp scramb", "tracking computer",
        "sensor booster", "guidance computer", "omnidirectional tracking", "remote ",
    ];
    if active_words.iter().any(|word| family.contains(word)) {
        return false;
    }
    if attr_value(attrs, &["capacitorNeed", "capacitorNeedHidden"])
        .is_some_and(|value| value != 0.0)
    {
        return false;
    }
    !(cycle_seconds(attrs).is_some()
        && ["hardener", "invulnerability", "reactive", "field", "booster", "repairer", "propulsion"]
            .iter()
            .any(|word| family.contains(word)))
}

fn item_effects_apply(
    item: &FittingStatsItem,
    attrs: &BTreeMap<String, f64>,
    group: &str,
    name: &str,
) -> bool {
    item_is_online(item) && (module_is_passive(item, attrs, group, name) || item_is_running(item))
}

fn extend(values: &mut Vec<f64>, value: Option<f64>, quantity: i64) {
    if let Some(value) = value.filter(|value| *value != 0.0) {
        values.extend(std::iter::repeat_n(value, quantity.max(0) as usize));
    }
}

fn dogma_extend(values: &mut Vec<f64>, value: Option<f64>, quantity: i64) {
    extend(values, dogma_multiplier(value), quantity);
}

fn cargo_capacity_multiplier(attrs: &BTreeMap<String, f64>, group: &str, name: &str) -> Option<f64> {
    let _ = (group, name);
    attr_value(attrs, &["cargoCapacityMultiplier"])
        .filter(|value| *value > 0.0)
        .or_else(|| attr_value(attrs, &["cargoCapacityBonus"]).map(|value| 1.0 + value / 100.0))
}

fn resistance_bonus_multiplier(values: &[f64]) -> f64 {
    let multipliers = values
        .iter()
        .copied()
        .filter(|value| *value != 0.0)
        .map(|value| {
            if value.abs() > 2.0 {
                (1.0 - value.abs() / 100.0).max(0.01)
            } else {
                (1.0 - (1.0 - value).abs()).max(0.01)
            }
        })
        .collect::<Vec<_>>();
    stacking_raw_multiplier(&multipliers)
}

fn apply_damage_multipliers(profile: &mut DamageProfile, values: &[Vec<f64>; 4], direct: bool) {
    let multipliers: [f64; 4] = std::array::from_fn(|index| {
        let entry = &values[index];
        if direct {
            stacking_multiplier(entry)
        } else {
            resistance_bonus_multiplier(entry)
        }
    });
    profile.em = (profile.em * multipliers[0]).clamp(0.01, 1.0);
    profile.thermal = (profile.thermal * multipliers[1]).clamp(0.01, 1.0);
    profile.kinetic = (profile.kinetic * multipliers[2]).clamp(0.01, 1.0);
    profile.explosive = (profile.explosive * multipliers[3]).clamp(0.01, 1.0);
}

#[derive(Default)]
struct ModuleModifiers {
    shield_add: f64,
    armor_add: f64,
    structure_add: f64,
    shield_percent: Vec<f64>,
    armor_percent: Vec<f64>,
    structure_percent: Vec<f64>,
    structure_multipliers: Vec<f64>,
    velocity: Vec<f64>,
    propulsion: Vec<(f64, f64, f64)>,
    signature: Vec<f64>,
    signature_add: f64,
    mass_add: f64,
    agility: Vec<f64>,
    capacitor: Vec<f64>,
    recharge: Vec<f64>,
    recharge_rig: Vec<f64>,
    cargo: Vec<f64>,
    shield_repair_hps: f64,
    armor_repair_hps: f64,
    structure_repair_hps: f64,
    shield_repair: Vec<f64>,
    armor_repair: Vec<f64>,
    armor_repair_cycle: Vec<f64>,
    structure_repair: Vec<f64>,
    missile_damage: Vec<f64>,
    missile_rof: Vec<f64>,
    missile_velocity: Vec<f64>,
    missile_flight_time: Vec<f64>,
    missile_range: Vec<f64>,
    turret_damage: Vec<f64>,
    turret_rof: Vec<f64>,
    turret_range: Vec<f64>,
    drone_damage: Vec<f64>,
    drone_range_bonus: f64,
    drone_range: Vec<f64>,
    capacitor_draw: f64,
    capacitor_modules: Vec<Value>,
    resonance_bonus: [[Vec<f64>; 4]; 3],
    resonance_direct: [[Vec<f64>; 4]; 3],
}

fn collect_module_modifiers(input: &FittingStatsInput) -> ModuleModifiers {
    let mut result = ModuleModifiers::default();
    let ship_attrs = normalized_attrs(&input.ship_attrs);
    let armor_rig_cycles = input.items.iter().filter_map(|item| {
        let group = input.group_names.get(&item.type_id)?.to_lowercase();
        (item_is_online(item) && group.contains("rig armor")).then(|| {
            input.dogma.get(&item.type_id).map(normalized_attrs)
                .and_then(|attrs| dogma_multiplier(attr_value(&attrs, &["durationSkillBonus"])))
        }).flatten()
    }).collect::<Vec<_>>();
    for item in &input.items {
        if !FITTED_SLOTS.contains(&slot_prefix(&item.flag))
            || (!input.stats_item_ids.is_empty() && !input.stats_item_ids.contains(&item.id))
            || !item_is_online(item)
        {
            continue;
        }
        let attrs = input.dogma.get(&item.type_id).map(normalized_attrs).unwrap_or_default();
        let group = input.group_names.get(&item.type_id).map(String::as_str).unwrap_or("");
        let name = input.names.get(&item.type_id).map(String::as_str).unwrap_or("");
        result.signature_add += attr_value(&attrs, &["signatureRadiusAdd"]).unwrap_or(0.0)
            * module_quantity(item) as f64;
        if !item_effects_apply(item, &attrs, group, name) {
            continue;
        }
        let qty = module_quantity(item);
        let quantity = qty as f64;
        let family = format!("{name} {group}").to_lowercase();
        let overheated = item_is_overheated(item, input.heat);

        if group.to_lowercase().contains("shield extender") {
            result.shield_add += attr_value(&attrs, &["capacityBonus"]).unwrap_or(0.0) * quantity;
        }
        result.shield_add += attr_value(&attrs, &["shieldCapacityBonusAdd"]).unwrap_or(0.0) * quantity;
        result.armor_add += attr_value(&attrs, &["armorHPBonusAdd"]).unwrap_or(0.0) * quantity;
        result.structure_add += attr_value(&attrs, &["hpBonusAdd", "structureHitpointBonusAdd"]).unwrap_or(0.0) * quantity;
        extend(&mut result.shield_percent, attr_value(&attrs, &["shieldCapacityBonus", "shieldCapacityBonus2"]), qty);
        extend(&mut result.armor_percent, attr_value(&attrs, &["armorHPBonus"]), qty);
        extend(&mut result.structure_percent, attr_value(&attrs, &["hpBonus", "structureHitpointBonus"]), qty);
        extend(&mut result.structure_multipliers, attr_value(&attrs, &["structureHPMultiplier"]), qty);

        dogma_extend(&mut result.velocity, attr_value(&attrs, &["maxVelocityModifier"]), qty);
        if family.contains("afterburner") || family.contains("microwarpdrive") || family.contains("propulsion") {
            if let Some(mut speed) = attr_value(&attrs, &["speedFactor", "maxVelocityBonus"]) {
                if overheated {
                    speed += attr_value(&attrs, &["overloadSpeedFactorBonus"]).unwrap_or(0.0);
                }
                result.propulsion.extend(std::iter::repeat_n((
                    speed,
                    attr_value(&attrs, &["speedBoostFactor"]).unwrap_or(0.0),
                    attr_value(&attrs, &["massAddition"]).unwrap_or(0.0),
                ), qty as usize));
            }
        }
        extend(
            &mut result.signature,
            attr_value(&attrs, &["signatureRadiusBonus"]).map(|value| 1.0 + value / 100.0),
            qty,
        );
        if group.to_lowercase().contains("rig shield") {
            if let Some(drawback) = attr_value(&attrs, &["drawback"]) {
                let mitigation = named_skill_dogma_multiplier(
                    input,
                    "Shield Rigging",
                    &["rigDrawbackBonus"],
                );
                extend(
                    &mut result.signature,
                    Some(1.0 + drawback * mitigation / 100.0),
                    qty,
                );
            }
        }
        result.mass_add += attr_value(&attrs, &["massAddition"]).unwrap_or(0.0) * quantity;
        dogma_extend(&mut result.agility, attr_value(&attrs, &["agilityMultiplier"]), qty);
        dogma_extend(&mut result.capacitor, attr_value(&attrs, &["capacitorCapacityMultiplier", "capacitorCapacityBonus"]), qty);
        dogma_extend(&mut result.recharge, attr_value(&attrs, &["capacitorRechargeRateMultiplier"]), qty);
        if group.to_lowercase().contains("rig") {
            dogma_extend(&mut result.recharge_rig, attr_value(&attrs, &["capRechargeBonus"]), qty);
        }
        extend(&mut result.cargo, cargo_capacity_multiplier(&attrs, group, name), qty);

        let missile_damage = attr_value(&attrs, &["missileDamageMultiplierBonus", "missileDamageMultiplier"]);
        extend(&mut result.missile_damage, missile_damage, qty);
        dogma_extend(&mut result.missile_rof, attr_value(&attrs, &["bastionMissileROFBonus"]), qty);
        dogma_extend(&mut result.turret_rof, attr_value(&attrs, &["bastionTurretROFBonus"]), qty);
        for attr in ["missileVelocityBonus", "missileVelocityMultiplier", "missileVelocityBonusBonus"] {
            dogma_extend(&mut result.missile_velocity, attr_value(&attrs, &[attr]), qty);
        }
        for attr in ["explosionDelayBonus", "flightTimeBonus", "explosionDelayBonusBonus"] {
            dogma_extend(&mut result.missile_flight_time, attr_value(&attrs, &[attr]), qty);
        }
        if let Some(range) = dogma_multiplier(attr_value(&attrs, &["maxRangeBonus", "rangeBonus", "rangeMultiplier"])) {
            if family.contains("bastion") || family.contains("tracking computer") || family.contains("range") {
                extend(&mut result.turret_range, Some(range), qty);
            }
            if family.contains("guidance computer") || family.contains("guidance enhancer") || family.contains("missile guidance") {
                extend(&mut result.missile_range, Some(range), qty);
            }
        }
        let mut turret_damage = attr_value(&attrs, &["damageMultiplierBonus"]);
        if turret_damage.is_none() && ["magnetic field stabilizer", "heat sink", "gyrostabilizer"].iter().any(|word| family.contains(word)) {
            turret_damage = attr_value(&attrs, &["damageMultiplier"]);
        }
        extend(&mut result.turret_damage, turret_damage, qty);
        extend(&mut result.drone_damage, attr_value(&attrs, &["droneDamageBonus", "droneDamageMultiplierBonus"]), qty);
        result.drone_range_bonus += attr_value(&attrs, &["droneRangeBonus", "droneControlRangeBonus", "droneControlDistanceBonus"]).unwrap_or(0.0) * quantity;
        dogma_extend(&mut result.drone_range, attr_value(&attrs, &["droneRangeMultiplier", "droneControlRangeMultiplier"]), qty);
        if let Some(mut speed) = attr_value(&attrs, &["speedMultiplier"]) {
            if overheated {
                speed *= 1.0 + attr_value(&attrs, &["overloadRofBonus"]).unwrap_or(0.0) / 100.0;
            }
            if missile_damage.is_some() || family.contains("ballistic") {
                extend(&mut result.missile_rof, Some(speed), qty);
            } else if turret_damage.is_some() || ["heat sink", "gyrostabilizer", "magnetic field"].iter().any(|word| family.contains(word)) {
                extend(&mut result.turret_rof, Some(speed), qty);
            }
        }

        if let Some(cycle) = cycle_seconds(&attrs) {
            if family.contains("shield booster") {
                result.shield_repair_hps += attr_value(&attrs, &["shieldBonus", "shieldBoostAmount"]).unwrap_or(0.0) / cycle * quantity;
            }
            if family.contains("armor repair") || family.contains("ancillary armor") {
                result.armor_repair_hps += attr_value(&attrs, &["armorDamageAmount", "armorHPRepaired"]).unwrap_or(0.0) / cycle * quantity;
            }
            if family.contains("hull repair") || family.contains("structure repair") {
                result.structure_repair_hps += attr_value(&attrs, &["structureDamageAmount", "hullDamageAmount", "hullRepairAmount"]).unwrap_or(0.0) / cycle * quantity;
            }
            if item_is_running(item) {
                let cap_need = attr_value(&attrs, &["capacitorNeed", "capacitorNeedHidden"]).unwrap_or(0.0).max(0.0);
                let charge_attrs = item.charge_type_id.and_then(|type_id| input.dogma.get(&type_id))
                    .map(normalized_attrs).unwrap_or_default();
                let mut cap_multiplier = 1.0;
                let mut cycle_multiplier = 1.0;
                if family.contains("afterburner") || family.contains("propulsion module") {
                    cap_multiplier *= named_skill_dogma_multiplier(input, "Fuel Conservation", &["capNeedBonus"]);
                    cap_multiplier *= named_skill_dogma_multiplier(input, "Afterburner", &["capNeedBonus"]);
                    cycle_multiplier *= named_skill_dogma_multiplier(input, "Afterburner", &["durationBonus"]);
                }
                if family.contains("shield booster") {
                    cap_multiplier *= named_skill_dogma_multiplier(input, "Shield Compensation", &["shieldBoostCapacitorBonus"]);
                }
                if is_turret(group) {
                    cap_multiplier *= named_skill_dogma_multiplier(input, "Controlled Bursts", &["capNeedBonus"]);
                    let (_, required_rof) = required_skill_combat_multipliers(
                        input,
                        if charge_attrs.is_empty() { vec![&attrs] } else { vec![&attrs, &charge_attrs] }.as_slice(),
                    );
                    let (_, hull_rof) = hull_weapon_multipliers(input, &ship_attrs, &attrs, item.type_id);
                    cycle_multiplier *= required_rof
                        * named_skill_dogma_multiplier(input, "Rapid Firing", &["rofBonus"])
                        * hull_rof;
                }
                if family.contains("armor repair") || family.contains("ancillary armor") {
                    cycle_multiplier *= named_skill_dogma_multiplier(input, "Repair Systems", &["durationSkillBonus"])
                        * stacking_raw_multiplier(&armor_rig_cycles);
                }
                let effective_cycle = cycle * cycle_multiplier;
                let gross = cap_need * cap_multiplier / effective_cycle * quantity;
                let injected = if name.to_lowercase().contains("capacitor booster") {
                    attr_value(&charge_attrs, &["capacitorBonus", "capacitorCapacityBonus", "capBonus"])
                        .unwrap_or(0.0).max(0.0) / effective_cycle * quantity
                } else { 0.0 };
                let draw = gross - injected;
                result.capacitor_draw += draw;
                if draw.abs() > 0.0001 {
                    result.capacitor_modules.push(serde_json::json!({
                        "name": name, "gj_per_second": draw,
                        "cycle_seconds": effective_cycle, "quantity": module_quantity(item)
                    }));
                }
            }
        }
        dogma_extend(&mut result.shield_repair, attr_value(&attrs, &["shieldBoostMultiplier", "shieldBoostBonus", "shieldBoosterBonus"]), qty);
        dogma_extend(&mut result.armor_repair, attr_value(&attrs, &["armorRepairMultiplier", "armorRepairAmountBonus", "armorRepairerAmountBonus", "armorDamageAmountBonus"]), qty);
        dogma_extend(&mut result.armor_repair_cycle, attr_value(&attrs, &["durationSkillBonus"]), qty);
        dogma_extend(&mut result.structure_repair, attr_value(&attrs, &["structureRepairMultiplier", "hullRepairMultiplier"]), qty);

        let default_layer = if attrs.keys().any(|name| name.starts_with("shield") && name.contains("resonance")) { Some(0) }
            else if attrs.keys().any(|name| name.starts_with("armor") && name.contains("resonance")) { Some(1) }
            else if attrs.keys().any(|name| (name.starts_with("hull") || !name.starts_with("shield") && !name.starts_with("armor")) && name.contains("damageresonance")) { Some(2) }
            else if family.contains("shield") { Some(0) }
            else if family.contains("armor") || family.contains("energized") || family.contains("plating") { Some(1) }
            else if family.contains("hull") || family.contains("damage control") { Some(2) }
            else { None };
        for (raw_name, value) in &attrs {
            let damage = ["em", "thermal", "kinetic", "explosive"]
                .iter().position(|kind| raw_name.contains(kind));
            let Some(damage) = damage else { continue };
            if raw_name.contains("resistancebonus") {
                if let Some(layer) = default_layer {
                    let passive = family.contains("resistance amplifier")
                        || family.contains("energized")
                        || family.contains("plating");
                    let mut effective_value = *value;
                    if passive && layer < 2 {
                        let damage_name = ["EM", "Thermal", "Kinetic", "Explosive"][damage];
                        let layer_name = ["Shield", "Armor"][layer];
                        let skill_name = format!("{damage_name} {layer_name} Compensation");
                        effective_value *= named_skill_dogma_multiplier(
                            input,
                            &skill_name,
                            &["hardeningBonus"],
                        );
                    }
                    if overheated {
                        effective_value *= 1.0
                            + attr_value(&attrs, &["overloadHardeningBonus"])
                                .unwrap_or(0.0)
                                / 100.0;
                    }
                    result.resonance_bonus[layer][damage]
                        .extend(std::iter::repeat_n(effective_value, qty as usize));
                }
            } else if raw_name.contains("resonance") {
                let layer = if raw_name.contains("shield") { Some(0) }
                    else if raw_name.contains("armor") { Some(1) }
                    else if raw_name.contains("hull") || raw_name.contains("structure") { Some(2) }
                    else { default_layer };
                if let Some(layer) = layer {
                    result.resonance_direct[layer][damage].extend(std::iter::repeat_n(*value, qty as usize));
                }
            }
        }
    }
    result.capacitor_draw = result.capacitor_draw.max(0.0);
    result.capacitor_modules.sort_by(|left, right| {
        right.get("gj_per_second").and_then(Value::as_f64).unwrap_or(0.0).abs()
            .partial_cmp(&left.get("gj_per_second").and_then(Value::as_f64).unwrap_or(0.0).abs())
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    result.capacitor_modules.truncate(8);
    result
}

fn skill_level(levels: &BTreeMap<i64, i64>, type_id: i64) -> i64 {
    levels.get(&type_id).copied().unwrap_or(0).clamp(0, 5)
}

fn named_skill_level(levels: &BTreeMap<String, i64>, names: &[&str]) -> i64 {
    let normalized = levels
        .iter()
        .map(|(name, level)| (normalize_attr(name), *level))
        .collect::<BTreeMap<_, _>>();
    names
        .iter()
        .map(|name| normalized.get(&normalize_attr(name)).copied().unwrap_or(0))
        .max()
        .unwrap_or(0)
        .clamp(0, 5)
}

fn named_skill_dogma_multiplier(
    input: &FittingStatsInput,
    skill_name: &str,
    attribute_names: &[&str],
) -> f64 {
    let target = normalize_attr(skill_name);
    let type_id = input
        .names
        .iter()
        .find_map(|(type_id, name)| (normalize_attr(name) == target).then_some(*type_id));
    let bonus = type_id
        .and_then(|type_id| input.dogma.get(&type_id))
        .map(normalized_attrs)
        .and_then(|attrs| attr_value(&attrs, attribute_names));
    per_level_bonus_multiplier(
        bonus,
        named_skill_level(&input.skill_name_levels, &[skill_name]),
    )
}

fn character_agility_multiplier(
    input: &FittingStatsInput,
    ship_attrs: &BTreeMap<String, f64>,
) -> f64 {
    let mut skill_ids = vec![SPACESHIP_COMMAND_TYPE_ID, EVASIVE_MANEUVERING_TYPE_ID];
    if attr_value(ship_attrs, &["advancedAgility"]).is_some() {
        skill_ids.push(ADVANCED_SPACESHIP_COMMAND_TYPE_ID);
    }
    skill_ids.into_iter().fold(1.0, |multiplier, type_id| {
        let bonus = input
            .dogma
            .get(&type_id)
            .map(normalized_attrs)
            .and_then(|attrs| attr_value(&attrs, &["agilityBonus"]));
        multiplier
            * per_level_bonus_multiplier(bonus, skill_level(&input.skill_levels, type_id))
    })
}

fn per_level_bonus_multiplier(value: Option<f64>, level: i64) -> f64 {
    if level <= 0 {
        return 1.0;
    }
    value
        .map(|number| (1.0 + number / 100.0 * level as f64).max(0.01))
        .unwrap_or(1.0)
}

fn damage_profile(attrs: &BTreeMap<String, f64>) -> DamageProfile {
    DamageProfile {
        em: attr_value(attrs, &["emDamage"]).unwrap_or(0.0),
        thermal: attr_value(attrs, &["thermalDamage"]).unwrap_or(0.0),
        kinetic: attr_value(attrs, &["kineticDamage"]).unwrap_or(0.0),
        explosive: attr_value(attrs, &["explosiveDamage"]).unwrap_or(0.0),
    }
}

fn resonance_profile(attrs: &BTreeMap<String, f64>, layer: &str) -> DamageProfile {
    let candidates: [[&str; 2]; 4] = match layer {
        "shield" => [
            ["shieldEmDamageResonance", "shieldEmDamageResonance"],
            ["shieldThermalDamageResonance", "shieldThermalDamageResonance"],
            ["shieldKineticDamageResonance", "shieldKineticDamageResonance"],
            ["shieldExplosiveDamageResonance", "shieldExplosiveDamageResonance"],
        ],
        "armor" => [
            ["armorEmDamageResonance", "armorEmDamageResonance"],
            ["armorThermalDamageResonance", "armorThermalDamageResonance"],
            ["armorKineticDamageResonance", "armorKineticDamageResonance"],
            ["armorExplosiveDamageResonance", "armorExplosiveDamageResonance"],
        ],
        _ => [
            ["emDamageResonance", "hullEmDamageResonance"],
            ["thermalDamageResonance", "hullThermalDamageResonance"],
            ["kineticDamageResonance", "hullKineticDamageResonance"],
            ["explosiveDamageResonance", "hullExplosiveDamageResonance"],
        ],
    };
    let value = |index: usize| {
        attr_value(attrs, &candidates[index])
            .unwrap_or(1.0)
            .clamp(0.01, 1.0)
    };
    DamageProfile {
        em: value(0),
        thermal: value(1),
        kinetic: value(2),
        explosive: value(3),
    }
}

fn resistance_profile(resonance: DamageProfile) -> DamageProfile {
    DamageProfile {
        em: (1.0 - resonance.em).clamp(0.0, 1.0),
        thermal: (1.0 - resonance.thermal).clamp(0.0, 1.0),
        kinetic: (1.0 - resonance.kinetic).clamp(0.0, 1.0),
        explosive: (1.0 - resonance.explosive).clamp(0.0, 1.0),
    }
}

fn ship_freighter_skill_multiplier(
    input: &FittingStatsInput,
    ship_attrs: &BTreeMap<String, f64>,
    bonus_attrs: &[&str],
) -> f64 {
    let Some(skill_type_id) = attr_value(ship_attrs, &["requiredSkill2"]).map(|value| value as i64)
    else {
        return 1.0;
    };
    per_level_bonus_multiplier(
        attr_value(ship_attrs, bonus_attrs),
        skill_level(&input.skill_levels, skill_type_id),
    )
}

fn apply_hull_resonance_effects(
    input: &FittingStatsInput,
    ship_attrs: &BTreeMap<String, f64>,
    resonances: &mut [&mut DamageProfile; 3],
) {
    let hull_skill_id = attr_value(ship_attrs, &["requiredSkill1"])
        .unwrap_or(0.0) as i64;
    let hull_level = skill_level(&input.skill_levels, hull_skill_id);
    if hull_level <= 0 {
        return;
    }
    for effect in input.dogma_effects.get(&input.ship_type_id).into_iter().flatten() {
        let Some(modifiers) = effect.get("modifier_info").and_then(Value::as_array) else {
            continue;
        };
        for modifier in modifiers {
            if modifier.get("operation").and_then(Value::as_i64) != Some(6) {
                continue;
            }
            let source = modifier.get("modifying_attribute_name").and_then(Value::as_str);
            let target = modifier.get("modified_attribute_name").and_then(Value::as_str)
                .map(normalize_attr).unwrap_or_default();
            if !target.contains("resonance") {
                continue;
            }
            let Some(value) = source.and_then(|source| attr_value(ship_attrs, &[source])) else {
                continue;
            };
            let multiplier = per_level_bonus_multiplier(Some(value), hull_level);
            let layer = if target.contains("shield") { 0 }
                else if target.contains("armor") { 1 }
                else { 2 };
            let profile = &mut resonances[layer];
            if target.contains("thermal") { profile.thermal *= multiplier; }
            else if target.contains("kinetic") { profile.kinetic *= multiplier; }
            else if target.contains("explosive") { profile.explosive *= multiplier; }
            else if target.contains("em") { profile.em *= multiplier; }
        }
    }
}

fn omni_ehp(hitpoints: f64, resists: &DamageProfile) -> f64 {
    if hitpoints <= 0.0 {
        return 0.0;
    }
    let average_damage_taken = [resists.em, resists.thermal, resists.kinetic, resists.explosive]
        .iter()
        .map(|value| (1.0 - value).max(0.01))
        .sum::<f64>()
        / 4.0;
    hitpoints / average_damage_taken
}

fn bay_capacity<'a>(attrs: &'a BTreeMap<String, f64>, key: &str) -> Option<f64> {
    match key {
        "Cargo" => attr_value(attrs, &["capacity", "cargoCapacity", "cargoHoldCapacity"]),
        "DroneBay" => attr_value(attrs, &["droneCapacity"]),
        "FighterBay" => attr_value(attrs, &["fighterCapacity", "fighterBayCapacity", "fighterHangarCapacity"]),
        "FuelBay" => attr_value(attrs, &["fuelBayCapacity"]),
        "FleetHangar" => attr_value(attrs, &["fleetHangarCapacity"]),
        "ShipMaintenanceBay" => attr_value(attrs, &["shipMaintenanceBayCapacity"]),
        "FleetMaintenanceBay" => attr_value(attrs, &["fleetMaintenanceBayCapacity"]),
        "InfrastructureBay" => attr_value(attrs, &["infrastructureBayCapacity"]),
        "OreHold" => attr_value(attrs, &["oreHoldCapacity"]),
        "MineralHold" => attr_value(attrs, &["mineralHoldCapacity"]),
        "GasHold" => attr_value(attrs, &["gasHoldCapacity"]),
        "IceHold" => attr_value(attrs, &["iceHoldCapacity"]),
        "AmmoHold" => attr_value(attrs, &["ammoHoldCapacity"]),
        "PlanetaryCommoditiesHold" => attr_value(attrs, &["planetaryCommoditiesHoldCapacity", "planetaryCommoditiesCapacity"]),
        "CommandCenterHold" => attr_value(attrs, &["commandCenterHoldCapacity"]),
        "QuafeHold" => attr_value(attrs, &["quafeHoldCapacity"]),
        _ => None,
    }
}

fn cargo_bays(
    input: &FittingStatsInput,
    attrs: &BTreeMap<String, f64>,
    effective_cargo_capacity: Option<f64>,
) -> Vec<CargoBayStats> {
    let labels = [
        ("Cargo", "Cargo hold"),
        ("DroneBay", "Drone bay"),
        ("FighterBay", "Fighter hangar"),
        ("FuelBay", "Fuel bay"),
        ("FleetHangar", "Fleet hangar"),
        ("ShipMaintenanceBay", "Ship maintenance bay"),
        ("FleetMaintenanceBay", "Fleet maintenance bay"),
        ("InfrastructureBay", "Infrastructure bay"),
        ("OreHold", "Ore hold"),
        ("MineralHold", "Mineral hold"),
        ("GasHold", "Gas hold"),
        ("IceHold", "Ice hold"),
        ("AmmoHold", "Ammo hold"),
        ("PlanetaryCommoditiesHold", "PI hold"),
        ("CommandCenterHold", "Command center hold"),
        ("QuafeHold", "Quafe hold"),
    ];
    let mut used = BTreeMap::<&str, f64>::new();
    for item in &input.items {
        let key = slot_prefix(&item.flag);
        if BAY_SLOTS.contains(&key) {
            *used.entry(key).or_default() += input.volumes.get(&item.type_id).copied().unwrap_or(0.0)
                * module_quantity(item) as f64;
        }
    }
    labels
        .into_iter()
        .filter_map(|(key, label)| {
            let used = used.get(key).copied().unwrap_or(0.0);
            let capacity = if key == "Cargo" {
                effective_cargo_capacity
                    .or_else(|| bay_capacity(attrs, key))
                    .or(input.ship_capacity)
            } else {
                bay_capacity(attrs, key)
            };
            if (capacity.is_none() || capacity.is_some_and(|value| value <= 0.0)) && used <= 0.0 {
                return None;
            }
            let ok = capacity.is_none_or(|value| used <= value + 0.0001);
            Some(CargoBayStats {
                key,
                label,
                used,
                capacity,
                ok,
                percent: capacity
                    .filter(|value| *value > 0.0)
                    .map(|value| (used / value * 100.0).min(999.0)),
            })
        })
        .collect()
}

fn is_launcher(group: &str) -> bool {
    let group = group.to_lowercase();
    group.contains("launcher") && !group.contains("rig launcher")
}

fn is_turret(group: &str) -> bool {
    let group = group.to_lowercase();
    group.contains("turret")
        || matches!(group.as_str(), "energy weapon" | "hybrid weapon" | "precursor weapon" | "projectile weapon")
}

fn is_drone(group: &str) -> bool {
    let group = group.to_lowercase();
    group.ends_with("drone") || group.contains("fighter")
}

fn charge_kind(name: &str, group: &str) -> &'static str {
    let family = format!("{name} {group}").to_lowercase();
    for (token, kind) in [
        ("light missile", "light missile"),
        ("heavy assault missile", "heavy assault missile"),
        ("heavy missile", "heavy missile"),
        ("cruise missile", "cruise missile"),
        ("torpedo", "torpedo"),
        ("rocket", "rocket"),
        ("missile", "missile"),
    ] {
        if family.contains(token) {
            return kind;
        }
    }
    if family.contains("hybrid") || family.contains("charge") { "hybrid charge" }
    else if family.contains("projectile") || family.contains("ammo") { "projectile ammo" }
    else if family.contains("frequency crystal") || family.contains("crystal") { "frequency crystal" }
    else if family.contains("bomb") { "bomb" }
    else { "charge" }
}

fn charge_compatible(
    input: &FittingStatsInput,
    module_attrs: &BTreeMap<String, f64>,
    module_name: &str,
    module_group: &str,
    charge_type_id: i64,
) -> bool {
    let charge_attrs = input.dogma.get(&charge_type_id).map(normalized_attrs).unwrap_or_default();
    let charge_name = input.names.get(&charge_type_id).map(String::as_str).unwrap_or("");
    let charge_group = input.group_names.get(&charge_type_id).map(String::as_str).unwrap_or("");
    let module = format!(" {module_name} {module_group} ").to_lowercase();
    let charge = format!(" {charge_name} {charge_group} ").to_lowercase();
    let allowed_groups = (1..=5)
        .filter_map(|index| attr_value(module_attrs, &[&format!("chargeGroup{index}")]).map(|value| value as i64))
        .collect::<BTreeSet<_>>();
    if !allowed_groups.is_empty()
        && input.group_ids.get(&charge_type_id).is_some_and(|group_id| !allowed_groups.contains(group_id))
    {
        return false;
    }
    if let (Some(module_size), Some(charge_size)) = (
        attr_value(module_attrs, &["chargeSize"]),
        attr_value(&charge_attrs, &["chargeSize"]),
    ) {
        if module_size as i64 != charge_size as i64 {
            return false;
        }
    }
    let charge_xl = charge.contains(" xl ") || charge.contains("extra large");
    let module_xl = module.contains(" xl ") || module.contains("capital") || module.contains("citadel");
    if charge.contains("script") {
        return ["tracking computer", "tracking link", "sensor booster", "remote sensor", "guidance computer", "guidance enhancer", "missile guidance", "omnidirectional tracking", "warp disruption field"]
            .iter().any(|token| module.contains(token));
    }
    if module.contains("capacitor booster") || module.contains("ancillary shield booster") {
        return charge.contains("cap booster") || charge.contains("capacitor booster");
    }
    if module.contains("rapid light") || module.contains("light missile") {
        return !charge_xl && charge.contains("light missile");
    }
    if module.contains("heavy assault") { return !charge_xl && charge.contains("heavy assault missile"); }
    if module.contains("heavy missile") { return !charge_xl && charge.contains("heavy missile") && !charge.contains("assault"); }
    if module.contains("cruise") { return charge.contains("cruise missile") && charge_xl == module_xl; }
    if module.contains("torpedo") { return charge.contains("torpedo") && charge_xl == module_xl; }
    if module.contains("rocket") { return !charge_xl && charge.contains("rocket"); }
    if module.contains("launcher") { return !charge_xl && ["missile", "rocket", "torpedo"].iter().any(|token| charge.contains(token)); }
    if module.contains("laser") { return charge.contains("frequency crystal") || charge.contains("laser crystal"); }
    if module.contains("railgun") || module.contains("blaster") || module.contains("hybrid") { return charge.contains("hybrid charge"); }
    if module.contains("autocannon") || module.contains("artillery") || module.contains("projectile") { return charge.contains("projectile ammo"); }
    false
}

fn matching_charge_type(
    input: &FittingStatsInput,
    module_attrs: &BTreeMap<String, f64>,
    module_name: &str,
    module_group: &str,
) -> Option<i64> {
    let module = format!("{module_name} {module_group}").to_lowercase();
    let preferences = [
        ("rapid light missile", "light missile"), ("light missile", "light missile"),
        ("heavy assault missile", "heavy assault missile"), ("heavy missile", "heavy missile"),
        ("cruise missile", "cruise missile"), ("torpedo", "torpedo"), ("rocket", "rocket"),
        ("missile", "missile"), ("hybrid", "hybrid charge"), ("railgun", "hybrid charge"),
        ("blaster", "hybrid charge"), ("projectile", "projectile ammo"),
        ("autocannon", "projectile ammo"), ("artillery", "projectile ammo"),
        ("laser", "frequency crystal"),
    ].into_iter().filter_map(|(token, kind)| module.contains(token).then_some(kind)).collect::<Vec<_>>();
    let compatible = input.items.iter()
        .filter(|item| slot_prefix(&item.flag) == "Cargo")
        .map(|item| item.type_id)
        .filter(|type_id| {
            let attrs = input.dogma.get(type_id).map(normalized_attrs).unwrap_or_default();
            let name = input.names.get(type_id).map(String::as_str).unwrap_or("");
            let group = input.group_names.get(type_id).map(String::as_str).unwrap_or("");
            (profile_total(&damage_profile(&attrs)) > 0.0 || format!("{name} {group}").to_lowercase().contains("script"))
                && charge_compatible(input, module_attrs, module_name, module_group, *type_id)
        })
        .collect::<Vec<_>>();
    for preference in preferences {
        if let Some(type_id) = compatible.iter().find(|type_id| {
            charge_kind(
                input.names.get(type_id).map(String::as_str).unwrap_or(""),
                input.group_names.get(type_id).map(String::as_str).unwrap_or(""),
            ) == preference
        }) {
            return Some(*type_id);
        }
    }
    compatible.first().copied()
}

fn profile_total(profile: &DamageProfile) -> f64 {
    profile.em + profile.thermal + profile.kinetic + profile.explosive
}

fn scaled_profile(profile: &DamageProfile, multiplier: f64) -> DamageProfile {
    DamageProfile {
        em: profile.em * multiplier,
        thermal: profile.thermal * multiplier,
        kinetic: profile.kinetic * multiplier,
        explosive: profile.explosive * multiplier,
    }
}

fn add_profile(target: &mut DamageProfile, source: &DamageProfile) {
    target.em += source.em;
    target.thermal += source.thermal;
    target.kinetic += source.kinetic;
    target.explosive += source.explosive;
}

fn weapon_range(
    module: &BTreeMap<String, f64>,
    charge: &BTreeMap<String, f64>,
    launcher: bool,
    missile_velocity_multiplier: f64,
    missile_flight_multiplier: f64,
    range_multiplier: f64,
) -> (Option<f64>, Option<f64>, Option<f64>, Option<f64>, Option<f64>) {
    let charge_range = dogma_multiplier(attr_value(charge, &["rangeMultiplier", "maxRangeBonus"]))
        .unwrap_or(1.0);
    if launcher {
        let velocity = attr_value(charge, &["maxVelocity", "entityCruiseSpeed", "velocity"])
            .map(|value| value * missile_velocity_multiplier);
        let flight = attr_value(charge, &["explosionDelay", "duration", "flightTime"])
            .map(|value| value / 1000.0 * missile_flight_multiplier);
        let range = velocity.zip(flight).map(|(velocity, flight)| velocity * flight * charge_range * range_multiplier);
        (range, range, None, velocity, flight)
    } else {
        let optimal = attr_value(module, &["maxRange", "optimalRange"])
            .map(|value| value * charge_range * range_multiplier);
        let falloff = attr_value(module, &["falloff", "falloffRange"])
            .map(|value| value * charge_range * range_multiplier);
        let range = (optimal.is_some() || falloff.is_some())
            .then_some(optimal.unwrap_or(0.0) + falloff.unwrap_or(0.0));
        (range, optimal, falloff, None, None)
    }
}

fn module_requires_skill(attrs: &BTreeMap<String, f64>, skill_type_id: i64) -> bool {
    (1..=6).any(|index| {
        attr_value(attrs, &[&format!("requiredSkill{index}")])
            .is_some_and(|value| value as i64 == skill_type_id)
    })
}

fn required_skill_combat_multipliers(
    input: &FittingStatsInput,
    attribute_sets: &[&BTreeMap<String, f64>],
) -> (f64, f64) {
    let mut damage = 1.0;
    let mut rof = 1.0;
    let mut seen = BTreeSet::new();
    for attrs in attribute_sets {
        for index in 1..=6 {
            let Some(skill_type_id) = attr_value(attrs, &[&format!("requiredSkill{index}")])
                .map(|value| value as i64)
                .filter(|type_id| *type_id > 0 && seen.insert(*type_id))
            else {
                continue;
            };
            let skill_attrs = input.dogma.get(&skill_type_id).map(normalized_attrs).unwrap_or_default();
            let level = skill_level(&input.skill_levels, skill_type_id);
            damage *= per_level_bonus_multiplier(
                attr_value(&skill_attrs, &["damageMultiplierBonus"]),
                level,
            );
            rof *= per_level_bonus_multiplier(
                attr_value(&skill_attrs, &["rofBonus", "turretSpeeBonus"]),
                level,
            );
        }
    }
    (damage, rof)
}

fn hull_weapon_multipliers(
    input: &FittingStatsInput,
    ship_attrs: &BTreeMap<String, f64>,
    module_attrs: &BTreeMap<String, f64>,
    module_type_id: i64,
) -> (f64, f64) {
    let hull_skill_id = attr_value(ship_attrs, &["requiredSkill1"]).unwrap_or(0.0) as i64;
    let hull_level = skill_level(&input.skill_levels, hull_skill_id);
    if hull_level <= 0 {
        return (1.0, 1.0);
    }
    let mut damage = 1.0;
    let mut rof = 1.0;
    let mut seen = BTreeSet::new();
    for effect in input.dogma_effects.get(&input.ship_type_id).into_iter().flatten() {
        let Some(modifiers) = effect.get("modifier_info").and_then(Value::as_array) else { continue };
        for modifier in modifiers {
            if modifier.get("operation").and_then(Value::as_i64) != Some(6) { continue; }
            let target = modifier.get("modified_attribute_name").and_then(Value::as_str)
                .map(normalize_attr).unwrap_or_default();
            if !matches!(target.as_str(), "damagemultiplier" | "speed") { continue; }
            let source = modifier.get("modifying_attribute_name").and_then(Value::as_str);
            let Some(source_value) = source.and_then(|name| attr_value(ship_attrs, &[name])) else { continue };
            let group_id = modifier.get("groupID").and_then(Value::as_i64);
            let required_skill_id = modifier.get("skillTypeID").and_then(Value::as_i64);
            let applies = group_id.is_some_and(|group_id| input.group_ids.get(&module_type_id) == Some(&group_id))
                || required_skill_id.is_some_and(|skill_id| module_requires_skill(module_attrs, skill_id));
            let multiplier = per_level_bonus_multiplier(Some(source_value), hull_level);
            let key = format!("{target}:{multiplier}:{group_id:?}:{required_skill_id:?}");
            if !applies || !seen.insert(key) { continue; }
            if target == "damagemultiplier" { damage *= multiplier; }
            else { rof *= multiplier; }
        }
    }
    (damage, rof)
}

fn evaluate_offense(
    input: &FittingStatsInput,
    modifiers: &ModuleModifiers,
) -> (OffenseStats, f64) {
    let missile_damage_multiplier = stacking_multiplier(&modifiers.missile_damage)
        * (1.0 + 0.02 * skill_level(&input.skill_levels, WARHEAD_UPGRADES_TYPE_ID) as f64);
    let missile_rof_multiplier = stacking_raw_multiplier(&modifiers.missile_rof)
        * (1.0 - 0.03 * skill_level(&input.skill_levels, RAPID_LAUNCH_TYPE_ID) as f64).max(0.01);
    let missile_velocity_multiplier = stacking_raw_multiplier(&modifiers.missile_velocity)
        * (1.0 + 0.1 * named_skill_level(&input.skill_name_levels, &["Missile Projection"]) as f64);
    let missile_flight_multiplier = stacking_raw_multiplier(&modifiers.missile_flight_time)
        * (1.0 + 0.1 * named_skill_level(&input.skill_name_levels, &["Missile Bombardment"]) as f64);
    let missile_range_multiplier = stacking_raw_multiplier(&modifiers.missile_range);
    let turret_damage_multiplier = stacking_multiplier(&modifiers.turret_damage)
        * named_skill_dogma_multiplier(input, "Surgical Strike", &["damageMultiplierBonus"]);
    let turret_rof_multiplier = stacking_raw_multiplier(&modifiers.turret_rof)
        * named_skill_dogma_multiplier(input, "Rapid Firing", &["rofBonus"]);
    let turret_range_multiplier = stacking_raw_multiplier(&modifiers.turret_range);
    let drone_damage_multiplier = stacking_multiplier(&modifiers.drone_damage)
        * (1.0 + 0.1 * named_skill_level(&input.skill_name_levels, &["Drone Interfacing"]) as f64);
    let drone_control_range = (attr_value(&normalized_attrs(&input.ship_attrs), &["droneControlDistance"]).unwrap_or(20_000.0)
        + 5_000.0 * named_skill_level(&input.skill_name_levels, &["Drone Avionics", "Scout Drone Operation"]) as f64
        + 3_000.0 * named_skill_level(&input.skill_name_levels, &["Advanced Drone Avionics", "Electronic Warfare Drone Interfacing"]) as f64
        + modifiers.drone_range_bonus)
        * stacking_raw_multiplier(&modifiers.drone_range);

    let mut result = OffenseStats::default();
    for item in &input.items {
        let slot = slot_prefix(&item.flag);
        let group = input.group_names.get(&item.type_id).map(String::as_str).unwrap_or("");
        let fitted_weapon = FITTED_SLOTS.contains(&slot) && (is_launcher(group) || is_turret(group) || group.to_lowercase().contains("smartbomb"));
        let drone = matches!(slot, "DroneBay" | "FighterBay") && is_drone(group) && item_is_running(item);
        if (!fitted_weapon && !drone)
            || !item_is_online(item)
            || (fitted_weapon && !input.stats_item_ids.is_empty() && !input.stats_item_ids.contains(&item.id))
        {
            continue;
        }
        let attrs = input.dogma.get(&item.type_id).map(normalized_attrs).unwrap_or_default();
        if fitted_weapon && !item_effects_apply(
            item,
            &attrs,
            group,
            input.names.get(&item.type_id).map(String::as_str).unwrap_or(""),
        ) {
            continue;
        }
        let module_name = input.names.get(&item.type_id).map(String::as_str).unwrap_or("");
        let charge_type_id = item.charge_type_id
            .filter(|type_id| charge_compatible(input, &attrs, module_name, group, *type_id))
            .or_else(|| matching_charge_type(input, &attrs, module_name, group));
        let charge_attrs = charge_type_id
            .and_then(|type_id| input.dogma.get(&type_id))
            .map(normalized_attrs)
            .unwrap_or_default();
        let base_profile = if profile_total(&damage_profile(&charge_attrs)) > 0.0 {
            damage_profile(&charge_attrs)
        } else {
            damage_profile(&attrs)
        };
        let base_damage = profile_total(&base_profile);
        let base_multiplier = attr_value(&attrs, &["damageMultiplier"]).unwrap_or(1.0);
        let cycle = cycle_seconds(&attrs);
        let quantity = module_quantity(item) as f64;
        let (mut damage_bonus, mut rof_bonus, range_bonus, velocity_bonus, flight_bonus) = if drone {
            (drone_damage_multiplier, 1.0, 1.0, 1.0, 1.0)
        } else if is_launcher(group) {
            (missile_damage_multiplier, missile_rof_multiplier, missile_range_multiplier, missile_velocity_multiplier, missile_flight_multiplier)
        } else {
            (turret_damage_multiplier, turret_rof_multiplier, turret_range_multiplier, 1.0, 1.0)
        };
        let (required_damage, required_rof) = required_skill_combat_multipliers(
            input,
            if charge_attrs.is_empty() { vec![&attrs] } else { vec![&attrs, &charge_attrs] }.as_slice(),
        );
        let ship_attrs = normalized_attrs(&input.ship_attrs);
        let (hull_damage, hull_rof) = hull_weapon_multipliers(
            input,
            &ship_attrs,
            &attrs,
            item.type_id,
        );
        damage_bonus *= required_damage * hull_damage;
        rof_bonus *= required_rof * hull_rof;
        let total_multiplier = base_multiplier * damage_bonus * quantity;
        let item_profile = scaled_profile(&base_profile, total_multiplier);
        let volley = base_damage * total_multiplier;
        let dps = cycle.filter(|cycle| *cycle > 0.0 && rof_bonus > 0.0)
            .map(|cycle| volley / (cycle * rof_bonus)).unwrap_or(0.0);
        let (range, optimal, falloff, missile_velocity, missile_flight) = if drone {
            let range = attr_value(&attrs, &["maxRange"]).or(Some(drone_control_range));
            (range, range, None, None, None)
        } else {
            weapon_range(&attrs, &charge_attrs, is_launcher(group), velocity_bonus, flight_bonus, range_bonus)
        };
        if drone { result.drone_dps += dps; }
        else if is_launcher(group) { result.launcher_dps += dps; }
        else { result.turret_dps += dps; }
        result.volley += volley;
        add_profile(&mut result.damage_types, &item_profile);
        result.max_range_m = match (result.max_range_m, range) {
            (Some(left), Some(right)) => Some(left.max(right)),
            (None, right) => right,
            (left, None) => left,
        };
        let drone_velocity = drone.then(|| {
            attr_value(&attrs, &["maxVelocity", "entityCruiseSpeed", "orbitVelocity"])
                .map(|value| value * (1.0 + 0.05 * named_skill_level(&input.skill_name_levels, &["Drone Navigation"]) as f64))
        }).flatten();
        let drone_repair = if drone {
            let amount = attr_value(&attrs, &["shieldBonus", "shieldTransferAmount", "shieldBoostAmount"]).unwrap_or(0.0)
                + attr_value(&attrs, &["armorDamageAmount", "armorHPRepaired", "armorTransferAmount"]).unwrap_or(0.0)
                + attr_value(&attrs, &["structureDamageAmount", "hullDamageAmount", "hullRepairAmount", "structureTransferAmount"]).unwrap_or(0.0);
            cycle.filter(|cycle| amount > 0.0 && *cycle > 0.0).map(|cycle| amount * quantity / cycle)
        } else { None };
        let drone_mining = if drone {
            attr_value(&attrs, &["miningAmount", "miningYield", "harvestAmount"])
                .map(|value| value * quantity * (1.0 + 0.05 * named_skill_level(&input.skill_name_levels, &["Mining Drone Operation"]) as f64))
        } else { None };
        let drone_salvage = drone.then(|| attr_value(&attrs, &["accessDifficultyBonus", "salvageAccessBonus", "salvageBonus"])).flatten();
        let drone_ecm = drone.then(|| [
            "scanRadarStrengthBonus", "radarStrengthBonus", "scanLadarStrengthBonus",
            "ladarStrengthBonus", "scanMagnetometricStrengthBonus", "magnetometricStrengthBonus",
            "scanGravimetricStrengthBonus", "gravimetricStrengthBonus", "ecmStrength", "ewarStrength",
        ].iter().map(|name| attr_value(&attrs, &[*name]).unwrap_or(0.0)).reduce(f64::max).unwrap_or(0.0))
            .filter(|value| *value > 0.0);
        let drone_scramble = drone.then(|| attr_value(&attrs, &["warpScrambleStrength", "warpScrambleMaxStrength"])).flatten();
        result.weapons.push(serde_json::json!({
            "item_id": item.id,
            "type_id": item.type_id,
            "name": input.names.get(&item.type_id).cloned().unwrap_or_else(|| format!("Type {}", item.type_id)),
            "group": group,
            "slot_flag": item.flag,
            "quantity": module_quantity(item),
            "dps": dps,
            "volley": volley,
            "charge_name": charge_type_id.and_then(|type_id| input.names.get(&type_id)).cloned(),
            "damage_types": item_profile,
            "state": item.simulation_state.to_lowercase(),
            "overheated": item_is_overheated(item, input.heat),
            "range_m": range,
            "optimal_m": optimal,
            "falloff_m": falloff,
            "missile_velocity_m_s": missile_velocity,
            "missile_flight_time_s": missile_flight,
            "control_range_m": if drone { Some(drone_control_range) } else { None },
            "velocity_m_s": drone_velocity,
            "repair_hps": drone_repair,
            "mining_yield": drone_mining,
            "salvage_bonus": drone_salvage,
            "ecm_strength": drone_ecm,
            "scramble_strength": drone_scramble,
        }));
    }
    result.total_dps = result.turret_dps + result.launcher_dps + result.drone_dps;
    result.weapon_count = result.weapons.len();
    result.weapons.sort_by(|left, right| {
        right.get("dps").and_then(Value::as_f64).unwrap_or(0.0)
            .partial_cmp(&left.get("dps").and_then(Value::as_f64).unwrap_or(0.0))
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    result.weapons.truncate(80);
    (result, drone_control_range)
}

pub fn evaluate_fitting_stats(input: FittingStatsInput) -> Result<FittingStatsOutput, String> {
    if input.schema_version != "eqm.fitting-stats-input.v1" {
        return Err(format!(
            "unsupported fitting stats schema: {}",
            input.schema_version
        ));
    }
    let ship_attrs = normalized_attrs(&input.ship_attrs);
    let modifiers = collect_module_modifiers(&input);
    let mut shield_hp = attr_value(&ship_attrs, &["shieldCapacity"]).unwrap_or(0.0) + modifiers.shield_add;
    let mut armor_hp = attr_value(&ship_attrs, &["armorHP"]).unwrap_or(0.0) + modifiers.armor_add;
    let mut structure_hp = attr_value(&ship_attrs, &["hp", "structureHP"]).unwrap_or(0.0) + modifiers.structure_add;
    shield_hp *= 1.0 + 0.05 * skill_level(&input.skill_levels, SHIELD_MANAGEMENT_TYPE_ID) as f64;
    armor_hp *= 1.0 + 0.05 * skill_level(&input.skill_levels, HULL_UPGRADES_TYPE_ID) as f64;
    structure_hp *= 1.0 + 0.05 * skill_level(&input.skill_levels, MECHANICS_TYPE_ID) as f64;
    shield_hp *= unpenalized_multiplier(&modifiers.shield_percent.iter().map(|value| 1.0 + value / 100.0).collect::<Vec<_>>());
    armor_hp *= unpenalized_multiplier(&modifiers.armor_percent.iter().map(|value| 1.0 + value / 100.0).collect::<Vec<_>>());
    structure_hp *= unpenalized_multiplier(&modifiers.structure_percent.iter().map(|value| 1.0 + value / 100.0).collect::<Vec<_>>());
    structure_hp *= unpenalized_multiplier(&modifiers.structure_multipliers);

    let mut shield_resonance = resonance_profile(&ship_attrs, "shield");
    let mut armor_resonance = resonance_profile(&ship_attrs, "armor");
    let mut structure_resonance = resonance_profile(&ship_attrs, "structure");
    apply_hull_resonance_effects(
        &input,
        &ship_attrs,
        &mut [&mut shield_resonance, &mut armor_resonance, &mut structure_resonance],
    );
    apply_damage_multipliers(&mut shield_resonance, &modifiers.resonance_direct[0], true);
    apply_damage_multipliers(&mut armor_resonance, &modifiers.resonance_direct[1], true);
    apply_damage_multipliers(&mut structure_resonance, &modifiers.resonance_direct[2], true);
    apply_damage_multipliers(&mut shield_resonance, &modifiers.resonance_bonus[0], false);
    apply_damage_multipliers(&mut armor_resonance, &modifiers.resonance_bonus[1], false);
    apply_damage_multipliers(&mut structure_resonance, &modifiers.resonance_bonus[2], false);
    let shield_resists = resistance_profile(shield_resonance);
    let armor_resists = resistance_profile(armor_resonance);
    let structure_resists = resistance_profile(structure_resonance);
    let shield_ehp = omni_ehp(shield_hp, &shield_resists);
    let armor_ehp = omni_ehp(armor_hp, &armor_resists);
    let structure_ehp = omni_ehp(structure_hp, &structure_resists);

    let mass = input.ship_mass.or_else(|| attr_value(&ship_attrs, &["mass"]))
        .map(|value| value + modifiers.mass_add);
    let inertia = attr_value(&ship_attrs, &["agility", "inertiaModifier"])
        .map(|value| {
            value
                * character_agility_multiplier(&input, &ship_attrs)
                * stacking_raw_multiplier(&modifiers.agility)
        });
    let align_time = mass
        .zip(inertia)
        .filter(|(mass, inertia)| *mass > 0.0 && *inertia > 0.0)
        .map(|(mass, inertia)| 1.38629436112 * mass * inertia / 1_000_000.0);
    let max_velocity = attr_value(&ship_attrs, &["maxVelocity"]).map(|value| {
        let mut result = value * (1.0 + 0.05 * skill_level(&input.skill_levels, NAVIGATION_TYPE_ID) as f64);
        let base_mass = input.ship_mass.or_else(|| attr_value(&ship_attrs, &["mass"]));
        if let Some(base_mass) = base_mass.filter(|mass| *mass > 0.0) {
            let acceleration = 1.0 + 0.05 * named_skill_level(&input.skill_name_levels, &["Acceleration Control"]) as f64;
            let best_propulsion = modifiers.propulsion.iter().filter_map(|(speed, thrust, mass_add)| {
                let effective_mass = base_mass + mass_add;
                (*thrust > 0.0 && effective_mass > 0.0)
                    .then_some(speed / 100.0 * acceleration * thrust / effective_mass)
            }).reduce(f64::max);
            if let Some(bonus) = best_propulsion {
                result *= 1.0 + bonus;
            }
        }
        result
            * ship_freighter_skill_multiplier(
                &input,
                &ship_attrs,
                &["freighterBonusA1", "freighterBonusC1", "freighterBonusG1", "freighterBonusM1"],
            )
            * stacking_raw_multiplier(&modifiers.velocity)
    });

    let capacitor_capacity = attr_value(&ship_attrs, &["capacitorCapacity"]).map(|value| {
        let bonus = input
            .dogma
            .get(&CAPACITOR_MANAGEMENT_TYPE_ID)
            .map(normalized_attrs)
            .and_then(|attrs| attr_value(&attrs, &["capacitorCapacityBonus"]));
        value * stacking_raw_multiplier(&modifiers.capacitor) * per_level_bonus_multiplier(
            bonus,
            skill_level(&input.skill_levels, CAPACITOR_MANAGEMENT_TYPE_ID),
        )
    });
    let recharge_time = attr_value(&ship_attrs, &["rechargeRate", "capacitorRechargeRate"])
        .map(|value| value / 1000.0)
        .map(|value| {
            let bonus = input
                .dogma
                .get(&CAPACITOR_SYSTEMS_OPERATION_TYPE_ID)
                .map(normalized_attrs)
                .and_then(|attrs| attr_value(&attrs, &["capRechargeBonus"]));
            value
                * per_level_bonus_multiplier(
                    bonus,
                    skill_level(&input.skill_levels, CAPACITOR_SYSTEMS_OPERATION_TYPE_ID),
                )
                * unpenalized_multiplier(&modifiers.recharge)
                * unpenalized_multiplier(&modifiers.recharge_rig)
        });
    let peak_recharge = capacitor_capacity
        .zip(recharge_time)
        .filter(|(capacity, recharge)| *capacity > 0.0 && *recharge > 0.0)
        .map(|(capacity, recharge)| capacity / recharge * 2.5);
    let stable_percent = match (capacitor_capacity, recharge_time) {
        (Some(capacity), Some(recharge)) => capacitor_stable_percent(capacity, recharge, modifiers.capacitor_draw),
        _ if modifiers.capacitor_draw <= 0.0 => Some(100.0),
        _ => None,
    };

    let mut shield_repair_hps = modifiers.shield_repair_hps * stacking_raw_multiplier(&modifiers.shield_repair);
    let mut armor_repair_hps = modifiers.armor_repair_hps * stacking_raw_multiplier(&modifiers.armor_repair);
    let structure_repair_hps = modifiers.structure_repair_hps * stacking_raw_multiplier(&modifiers.structure_repair);
    let armor_cycle = stacking_raw_multiplier(&modifiers.armor_repair_cycle);
    if armor_cycle > 0.0 {
        armor_repair_hps /= armor_cycle;
    }
    if !shield_repair_hps.is_finite() { shield_repair_hps = 0.0; }

    let cargo_capacity = bay_capacity(&ship_attrs, "Cargo")
        .or(input.ship_capacity)
        .map(|value| {
            value
                * ship_freighter_skill_multiplier(
                    &input,
                    &ship_attrs,
                    &["freighterBonusA2", "freighterBonusC2", "freighterBonusG2", "freighterBonusM2"],
                )
                * unpenalized_multiplier(&modifiers.cargo)
        });
    let (offense, drone_control_range) = evaluate_offense(&input, &modifiers);

    let targeting_range = attr_value(&ship_attrs, &["maxTargetRange"]).map(|value| {
        value * (1.0 + 0.05 * named_skill_level(&input.skill_name_levels, &["Long Range Targeting"]) as f64)
    });
    let scan_resolution = attr_value(&ship_attrs, &["scanResolution"]).map(|value| {
        value * (1.0 + 0.05 * named_skill_level(&input.skill_name_levels, &["Signature Analysis"]) as f64)
    });
    let sensor_strength = [
        ("scanRadarStrength", "Radar Sensor Compensation"),
        ("scanLadarStrength", "Ladar Sensor Compensation"),
        ("scanMagnetometricStrength", "Magnetometric Sensor Compensation"),
        ("scanGravimetricStrength", "Gravimetric Sensor Compensation"),
    ]
    .into_iter()
    .map(|(attr, skill)| {
        attr_value(&ship_attrs, &[attr]).unwrap_or(0.0)
            * (1.0 + 0.04 * named_skill_level(&input.skill_name_levels, &[skill]) as f64)
    })
    .reduce(f64::max);

    Ok(FittingStatsOutput {
        schema_version: "eqm.fitting-stats-output.v1",
        offense,
        defense: DefenseStats {
            shield_hp,
            armor_hp,
            structure_hp,
            ehp: shield_ehp + armor_ehp + structure_ehp,
            shield_ehp,
            armor_ehp,
            structure_ehp,
            shield_resists,
            armor_resists,
            structure_resists,
            shield_peak_recharge: attr_value(&ship_attrs, &["shieldRechargeRate"])
                .filter(|value| *value > 0.0)
                .map(|recharge_ms| {
                    let skill = named_skill_dogma_multiplier(
                        &input,
                        "Shield Operation",
                        &["rechargeratebonus"],
                    );
                    shield_hp / (recharge_ms / 1000.0 * skill) * 2.5
                }),
            active_tank_hps: shield_repair_hps + armor_repair_hps + structure_repair_hps,
            shield_repair_hps,
            armor_repair_hps,
            structure_repair_hps,
        },
        mobility: MobilityStats {
            max_velocity,
            warp_speed: attr_value(&ship_attrs, &["warpSpeedMultiplier", "baseWarpSpeed"]),
            align_time,
            signature_radius: attr_value(&ship_attrs, &["signatureRadius"])
                .map(|value| (value + modifiers.signature_add) * stacking_raw_multiplier(&modifiers.signature)),
            mass,
            implant_modifiers_applied: 0,
        },
        capacitor: CapacitorStats {
            capacity: capacitor_capacity,
            recharge_time,
            peak_recharge,
            draw_per_second: modifiers.capacitor_draw,
            stable: stable_percent.is_some(),
            stable_percent,
            depletion_seconds: capacitor_capacity
                .zip(recharge_time)
                .and_then(|(capacity, recharge)| capacitor_depletion_seconds(capacity, recharge, modifiers.capacitor_draw)),
            modules: modifiers.capacitor_modules,
        },
        cargo_bays: cargo_bays(&input, &ship_attrs, cargo_capacity),
        targeting: TargetingStats {
            max_targets: attr_value(&ship_attrs, &["maxLockedTargets"]),
            targeting_range,
            scan_resolution,
            sensor_strength,
            drone_control_range_m: Some(drone_control_range),
        },
        notes: vec!["Combat stats are SDE-derived Rust estimates with fitted module state, character and required skills, hull Dogma effects, heat, capacitor draw, cargo, and stacking penalties.".to_string()],
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn foundational_helpers_match_expected_eve_math() {
        let attrs = normalized_attrs(&BTreeMap::from([
            ("emDamage".to_string(), 12.0),
            ("thermalDamage".to_string(), 8.0),
        ]));
        let profile = damage_profile(&attrs);
        assert_eq!(profile.em, 12.0);
        assert_eq!(profile.thermal, 8.0);
        assert_eq!(profile.kinetic, 0.0);
        assert_eq!(slot_prefix("HiSlot3"), "HiSlot");
        assert_eq!(dogma_multiplier(Some(25.0)), Some(1.25));
        assert!(stacking_raw_multiplier(&[1.25, 1.25]) < 1.25 * 1.25);
        assert!(stacking_multiplier(&[25.0, 25.0]) > 1.0);
        assert_eq!(unpenalized_multiplier(&[1.1, 1.2]), 1.32);
    }

    #[test]
    fn item_states_are_normalized() {
        let mut item = FittingStatsItem {
            id: 1,
            type_id: 2,
            charge_type_id: None,
            flag: "HiSlot0".to_string(),
            quantity: 99,
            simulation_state: "active".to_string(),
        };
        assert!(item_is_online(&item));
        assert!(item_is_running(&item));
        assert_eq!(module_quantity(&item), 1);
        item.simulation_state = "offline".to_string();
        assert!(!item_is_online(&item));
    }
}
