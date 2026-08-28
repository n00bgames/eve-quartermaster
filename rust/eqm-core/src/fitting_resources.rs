use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};

const CPU_MANAGEMENT_TYPE_ID: i64 = 3426;
const POWER_GRID_MANAGEMENT_TYPE_ID: i64 = 3413;
const WEAPON_UPGRADES_TYPE_ID: i64 = 3318;
const ADVANCED_WEAPON_UPGRADES_TYPE_ID: i64 = 11207;
const MEDIUM_HYBRID_TURRET_TYPE_ID: i64 = 3304;
const MINING_UPGRADES_TYPE_ID: i64 = 22578;
const SHIELD_UPGRADES_TYPE_ID: i64 = 3425;
const ENERGY_GRID_UPGRADES_TYPE_ID: i64 = 3424;

const SLOT_CAPACITIES: [(&str, &str); 6] = [
    ("HiSlot", "hiSlots"),
    ("MedSlot", "medSlots"),
    ("LoSlot", "lowSlots"),
    ("RigSlot", "rigSlots"),
    ("SubSystemSlot", "subSystemSlot"),
    ("ServiceSlot", "serviceSlots"),
];
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

const SUBSYSTEM_ADDITIVE_ATTRS: [(&str, &str); 14] = [
    ("hiSlots", "hiSlotModifier"),
    ("medSlots", "medSlotModifier"),
    ("lowSlots", "lowSlotModifier"),
    ("cpuOutput", "cpuOutput"),
    ("powerOutput", "powerOutput"),
    ("capacitorCapacity", "capacitorCapacity"),
    ("shieldCapacity", "shieldCapacity"),
    ("droneCapacity", "droneCapacity"),
    ("maxLockedTargets", "maxLockedTargetsBonus"),
    ("maxTargetRange", "maxTargetRange"),
    ("capacity", "cargoCapacityAdd"),
    ("cloakingCpuNeedBonus", "cloakingCpuNeedBonus"),
    (
        "subsystemMHTFittingReduction",
        "subsystemMHTFittingReduction",
    ),
    (
        "subsystemMMissileFittingReduction",
        "subsystemMMissileFittingReduction",
    ),
];
const SUBSYSTEM_PERCENT_ATTRS: [(&str, &str); 2] = [
    ("cpuOutput", "cpuOutputBonus2"),
    ("powerOutput", "powerEngineeringOutputBonus"),
];

#[derive(Clone, Debug, Deserialize)]
pub struct FittingResourcesInput {
    pub schema_version: String,
    #[serde(default)]
    pub ship_attrs: BTreeMap<String, f64>,
    #[serde(default)]
    pub skill_levels: BTreeMap<i64, i64>,
    #[serde(default)]
    pub items: Vec<FittingResourceItem>,
}

#[derive(Clone, Debug, Deserialize)]
pub struct FittingResourceItem {
    pub id: i64,
    pub type_id: i64,
    pub flag: String,
    #[serde(default = "default_quantity")]
    pub quantity: i64,
    #[serde(default = "default_state")]
    pub simulation_state: String,
    pub name: String,
    #[serde(default)]
    pub group_name: String,
    #[serde(default)]
    pub attrs: BTreeMap<String, f64>,
}

fn default_quantity() -> i64 {
    1
}

fn default_state() -> String {
    "online".to_string()
}

#[derive(Clone, Debug, Serialize)]
pub struct FittingResourcesOutput {
    pub schema_version: &'static str,
    pub effective_ship_attrs: BTreeMap<&'static str, Option<f64>>,
    pub resources: BTreeMap<&'static str, ResourceRow>,
    pub slots: Vec<SlotRow>,
    pub item_usage: Vec<ItemUsage>,
    pub stats_item_ids: Vec<i64>,
}

#[derive(Clone, Debug, Serialize)]
pub struct ResourceRow {
    pub used: f64,
    pub capacity: Option<f64>,
    pub ok: bool,
    pub percent: Option<f64>,
}

#[derive(Clone, Debug, Serialize)]
pub struct SlotRow {
    pub key: &'static str,
    pub used: i64,
    pub capacity: Option<i64>,
    pub ok: bool,
}

#[derive(Clone, Debug, Serialize)]
pub struct ItemUsage {
    pub id: i64,
    pub cpu: f64,
    pub powergrid: f64,
    pub calibration: f64,
}

fn normalize_attr(name: &str) -> String {
    name.to_lowercase()
        .chars()
        .filter(|character| character.is_ascii_alphanumeric())
        .collect()
}

fn normalized_attrs(attrs: BTreeMap<String, f64>) -> BTreeMap<String, f64> {
    attrs
        .into_iter()
        .map(|(name, value)| (normalize_attr(&name), value))
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

fn item_is_online(item: &FittingResourceItem) -> bool {
    item.simulation_state.to_lowercase() != "offline"
}

fn module_quantity(item: &FittingResourceItem) -> i64 {
    if FITTED_SLOTS.contains(&slot_prefix(&item.flag)) {
        1
    } else {
        item.quantity.max(1)
    }
}

fn skill_level(skill_levels: &BTreeMap<i64, i64>, type_id: i64) -> i64 {
    skill_levels.get(&type_id).copied().unwrap_or(0).clamp(0, 5)
}

fn is_launcher_group(group_name: &str) -> bool {
    group_name.to_lowercase().contains("launcher")
}

fn is_turret_group(group_name: &str) -> bool {
    let normalized = group_name.to_lowercase();
    normalized.contains("turret")
        || [
            "energy weapon",
            "hybrid weapon",
            "precursor weapon",
            "projectile weapon",
        ]
        .contains(&normalized.as_str())
}

fn is_weapon_group(group_name: &str) -> bool {
    is_turret_group(group_name)
        || is_launcher_group(group_name)
        || group_name.to_lowercase().contains("smartbomb")
}

fn module_requires_skill(attrs: &BTreeMap<String, f64>, skill_type_id: i64) -> bool {
    (1..=6).any(|index| {
        attr_value(attrs, &[&format!("requiredSkill{index}")])
            .is_some_and(|value| value as i64 == skill_type_id)
    })
}

fn effective_ship_attrs(
    ship_attrs: BTreeMap<String, f64>,
    items: &[FittingResourceItem],
) -> BTreeMap<String, f64> {
    let mut effective = normalized_attrs(ship_attrs);
    let subsystems = items
        .iter()
        .filter(|item| slot_prefix(&item.flag) == "SubSystemSlot" && item_is_online(item))
        .collect::<Vec<_>>();
    for item in &subsystems {
        let quantity = item.quantity.max(1) as f64;
        for (target, source) in SUBSYSTEM_ADDITIVE_ATTRS {
            if let Some(value) = attr_value(&item.attrs, &[source]) {
                *effective.entry(normalize_attr(target)).or_default() += value * quantity;
            }
        }
    }
    for item in &subsystems {
        for (target, source) in SUBSYSTEM_PERCENT_ATTRS {
            if let Some(value) = attr_value(&item.attrs, &[source]) {
                let key = normalize_attr(target);
                let current = effective.get(&key).copied().unwrap_or(0.0);
                effective.insert(key, current * (1.0 + value / 100.0).max(0.0));
            }
        }
    }
    let subsystem_slot = normalize_attr("subSystemSlot");
    let current = effective.get(&subsystem_slot).copied().unwrap_or(0.0);
    effective.insert(subsystem_slot, current.max(subsystems.len() as f64));
    effective
}

fn item_resource_usage(
    item: &FittingResourceItem,
    skill_levels: &BTreeMap<i64, i64>,
    ship_attrs: &BTreeMap<String, f64>,
) -> ItemUsage {
    let slot = slot_prefix(&item.flag);
    if !FITTED_SLOTS.contains(&slot) || !item_is_online(item) {
        return ItemUsage {
            id: item.id,
            cpu: 0.0,
            powergrid: 0.0,
            calibration: 0.0,
        };
    }
    let quantity = module_quantity(item) as f64;
    let mut cpu = attr_value(&item.attrs, &["cpu"]).unwrap_or(0.0);
    let mut powergrid = attr_value(&item.attrs, &["power", "powergridUsage"]).unwrap_or(0.0);
    if is_weapon_group(&item.group_name) {
        cpu *= (1.0 - 0.05 * skill_level(skill_levels, WEAPON_UPGRADES_TYPE_ID) as f64).max(0.0);
        powergrid *= (1.0
            - 0.02 * skill_level(skill_levels, ADVANCED_WEAPON_UPGRADES_TYPE_ID) as f64)
            .max(0.0);
    }
    if item.group_name.to_lowercase().contains("mining upgrade") {
        cpu *= (1.0 - 0.05 * skill_level(skill_levels, MINING_UPGRADES_TYPE_ID) as f64).max(0.0);
    }
    if item.group_name.to_lowercase().contains("shield extender") {
        powergrid *=
            (1.0 - 0.05 * skill_level(skill_levels, SHIELD_UPGRADES_TYPE_ID) as f64).max(0.0);
    }
    if module_requires_skill(&item.attrs, ENERGY_GRID_UPGRADES_TYPE_ID) {
        cpu *=
            (1.0 - 0.05 * skill_level(skill_levels, ENERGY_GRID_UPGRADES_TYPE_ID) as f64).max(0.0);
    }

    let family = format!("{} {}", item.name, item.group_name).to_lowercase();
    if family.contains("probe launcher") {
        if let Some(bonus) = attr_value(ship_attrs, &["roleBonusT3ProbeCPU"]) {
            cpu *= (1.0 + bonus / 100.0).max(0.0);
        }
    }
    if family.contains("covert ops cloaking") || family.contains("covert ops cloak") {
        if let Some(bonus) = attr_value(ship_attrs, &["cloakingCpuNeedBonus"]) {
            cpu = bonus.max(0.0);
        }
    }
    if family.contains("reinforced bulkhead") {
        if let Some(bonus) = attr_value(ship_attrs, &["cpuNeedBonus"]) {
            cpu *= (1.0 + bonus / 100.0).max(0.0);
        }
    }
    if let Some(reduction) = attr_value(ship_attrs, &["subsystemMHTFittingReduction"]) {
        if module_requires_skill(&item.attrs, MEDIUM_HYBRID_TURRET_TYPE_ID) {
            let multiplier = (1.0 + reduction / 100.0).max(0.0);
            cpu *= multiplier;
            powergrid *= multiplier;
        }
    }
    if let Some(reduction) = attr_value(ship_attrs, &["subsystemMMissileFittingReduction"]) {
        if is_launcher_group(&item.group_name) {
            let multiplier = (1.0 + reduction / 100.0).max(0.0);
            cpu *= multiplier;
            powergrid *= multiplier;
        }
    }

    ItemUsage {
        id: item.id,
        cpu: cpu * quantity,
        powergrid: powergrid * quantity,
        calibration: if slot == "RigSlot" {
            attr_value(&item.attrs, &["upgradeCost"]).unwrap_or(0.0) * quantity
        } else {
            0.0
        },
    }
}

pub fn evaluate_fitting_resources(
    mut input: FittingResourcesInput,
) -> Result<FittingResourcesOutput, String> {
    if input.schema_version != "eqm.fitting-resources-input.v1" {
        return Err(format!(
            "unsupported fitting resources schema: {}",
            input.schema_version
        ));
    }
    for item in &mut input.items {
        item.attrs = normalized_attrs(std::mem::take(&mut item.attrs));
    }
    let ship_attrs = effective_ship_attrs(input.ship_attrs, &input.items);
    let cpu_capacity = attr_value(&ship_attrs, &["cpuOutput"]).map(|value| {
        value * (1.0 + 0.05 * skill_level(&input.skill_levels, CPU_MANAGEMENT_TYPE_ID) as f64)
    });
    let powergrid_capacity = attr_value(&ship_attrs, &["powerOutput"]).map(|value| {
        value
            * (1.0 + 0.05 * skill_level(&input.skill_levels, POWER_GRID_MANAGEMENT_TYPE_ID) as f64)
    });
    let calibration_capacity = attr_value(&ship_attrs, &["upgradeCapacity"]);

    let item_usage = input
        .items
        .iter()
        .map(|item| item_resource_usage(item, &input.skill_levels, &ship_attrs))
        .collect::<Vec<_>>();
    let used_cpu = item_usage.iter().map(|row| row.cpu).sum::<f64>();
    let used_powergrid = item_usage.iter().map(|row| row.powergrid).sum::<f64>();
    let used_calibration = item_usage.iter().map(|row| row.calibration).sum::<f64>();

    let make_resource = |used: f64, capacity: Option<f64>| ResourceRow {
        used,
        capacity,
        ok: capacity.is_none_or(|value| used <= value),
        percent: capacity
            .filter(|value| *value != 0.0)
            .map(|value| (used / value * 100.0).min(999.0)),
    };
    let resources = BTreeMap::from([
        ("cpu", make_resource(used_cpu, cpu_capacity)),
        (
            "powergrid",
            make_resource(used_powergrid, powergrid_capacity),
        ),
        (
            "calibration",
            make_resource(used_calibration, calibration_capacity),
        ),
    ]);

    let mut slot_counts = BTreeMap::<&str, i64>::new();
    for item in &input.items {
        let slot = slot_prefix(&item.flag);
        if FITTED_SLOTS.contains(&slot) {
            *slot_counts.entry(slot).or_default() += module_quantity(item);
        }
    }
    let slots = SLOT_CAPACITIES
        .iter()
        .map(|(key, attr_name)| {
            let capacity = attr_value(&ship_attrs, &[*attr_name]).map(|value| value as i64);
            let used = slot_counts.get(*key).copied().unwrap_or(0);
            SlotRow {
                key: *key,
                used,
                capacity,
                ok: capacity.is_none_or(|value| used <= value),
            }
        })
        .collect();

    let mut ordered_items = input.items.iter().collect::<Vec<_>>();
    ordered_items.sort_by_key(|item| (slot_prefix(&item.flag), item.flag.as_str(), item.id));
    let mut accepted_counts = BTreeMap::<&str, i64>::new();
    let mut stats_item_ids = Vec::new();
    for item in ordered_items {
        let slot = slot_prefix(&item.flag);
        let Some((_, attr_name)) = SLOT_CAPACITIES.iter().find(|(key, _)| *key == slot) else {
            stats_item_ids.push(item.id);
            continue;
        };
        let capacity = attr_value(&ship_attrs, &[*attr_name]).map(|value| value as i64);
        let count = accepted_counts.get(slot).copied().unwrap_or(0);
        if capacity.is_none_or(|value| count < value) {
            stats_item_ids.push(item.id);
        }
        *accepted_counts.entry(slot).or_default() += module_quantity(item);
    }

    let effective_ship_attrs = BTreeMap::from([
        ("cpuOutput", attr_value(&ship_attrs, &["cpuOutput"])),
        ("powerOutput", attr_value(&ship_attrs, &["powerOutput"])),
        ("hiSlots", attr_value(&ship_attrs, &["hiSlots"])),
        (
            "subsystemMHTFittingReduction",
            attr_value(&ship_attrs, &["subsystemMHTFittingReduction"]),
        ),
        (
            "subsystemMMissileFittingReduction",
            attr_value(&ship_attrs, &["subsystemMMissileFittingReduction"]),
        ),
    ]);

    Ok(FittingResourcesOutput {
        schema_version: "eqm.fitting-resources-output.v1",
        effective_ship_attrs,
        resources,
        slots,
        item_usage,
        stats_item_ids,
    })
}
