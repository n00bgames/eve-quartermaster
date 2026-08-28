use std::cmp::Ordering;
use std::collections::{BTreeMap, BTreeSet};

use serde::{Deserialize, Serialize};

pub const PLANETARY_SHORTAGE_REPORT_SCHEMA: &str = "eqm.planetary-shortage-report.v1";

#[derive(Clone, Debug, Deserialize)]
pub struct PlanetaryIndustryPayload {
    pub as_of: String,
    #[serde(default)]
    pub schematics: Vec<PlanetarySchematic>,
    #[serde(default)]
    pub colonies: Vec<PlanetaryColony>,
}

#[derive(Clone, Debug, Deserialize)]
pub struct PlanetaryColony {
    #[serde(default)]
    pub pins: Vec<PlanetaryPin>,
}

#[derive(Clone, Debug, Deserialize)]
pub struct PlanetaryPin {
    #[serde(default)]
    pub projected_status: String,
    #[serde(default)]
    pub is_factory: bool,
    #[serde(default)]
    pub contents: Vec<PlanetaryPinContent>,
    pub extractor: Option<PlanetaryExtractor>,
    pub schematic: Option<PlanetarySchematic>,
}

#[derive(Clone, Debug, Deserialize)]
pub struct PlanetaryPinContent {
    pub type_id: u64,
    pub name: String,
    pub amount: f64,
}

#[derive(Clone, Debug, Deserialize)]
pub struct PlanetaryExtractor {
    pub product_type_id: Option<u64>,
    pub product_name: Option<String>,
    #[serde(default)]
    pub projected_daily_output: f64,
}

#[derive(Clone, Debug, Deserialize)]
pub struct PlanetarySchematic {
    pub id: u64,
    pub name: String,
    pub cycle_time: f64,
    pub output: PlanetaryMaterial,
    #[serde(default)]
    pub inputs: Vec<PlanetaryMaterial>,
}

#[derive(Clone, Debug, Deserialize)]
pub struct PlanetaryMaterial {
    pub type_id: u64,
    pub name: String,
    pub quantity: f64,
}

#[derive(Clone, Debug, Serialize)]
pub struct PlanetaryShortageReport {
    pub schema_version: &'static str,
    pub generated_at: String,
    pub source_as_of: String,
    pub methodology: &'static str,
    pub scope: PlanetaryShortageScope,
    pub summary: PlanetaryShortageSummary,
    pub commodities: Vec<PlanetaryShortageRow>,
    pub caveats: Vec<&'static str>,
}

#[derive(Clone, Debug, Serialize)]
pub struct PlanetaryShortageScope {
    pub target_type_id: Option<u64>,
    pub target_name: Option<String>,
    pub configured_target_factories: u64,
    pub configured_target_output_per_day: f64,
    pub commodity_count: usize,
}

#[derive(Clone, Debug, Serialize)]
pub struct PlanetaryShortageSummary {
    pub critical_shortages: usize,
    pub shortages: usize,
    pub watch_items: usize,
    pub covered_items: usize,
}

#[derive(Clone, Debug, Serialize)]
pub struct PlanetaryShortageRow {
    pub type_id: u64,
    pub name: String,
    pub projected_inventory: f64,
    pub configured_supply_per_day: f64,
    pub configured_demand_per_day: f64,
    pub net_shortfall_per_day: f64,
    pub coverage: Option<f64>,
    pub inventory_days_at_demand: Option<f64>,
    pub runway_days_at_net_shortfall: Option<f64>,
    pub configured_producers: u64,
    pub configured_consumers: u64,
    pub running_producers: u64,
    pub starved_producers: u64,
    pub producer_output_per_day: Option<f64>,
    pub additional_processors_to_balance: Option<u64>,
    pub base_components: Vec<BaseComponent>,
    pub severity: &'static str,
}

#[derive(Clone, Debug, Serialize)]
pub struct BaseComponent {
    pub type_id: u64,
    pub name: String,
    pub quantity_per_day: f64,
    pub planet_types: Vec<&'static str>,
}

#[derive(Clone, Debug)]
pub struct PlanetaryShortageTarget {
    pub type_id: u64,
    pub name: String,
    pub configured_factories: u64,
    pub configured_output_per_day: f64,
}

#[derive(Clone, Debug, Default)]
struct Aggregate {
    type_id: u64,
    name: String,
    inventory: f64,
    supply_per_day: f64,
    demand_per_day: f64,
    producers: u64,
    consumers: u64,
    running_producers: u64,
    starved_producers: u64,
    producer_output_per_day: Option<f64>,
}

fn per_day(quantity: f64, cycle_time: f64) -> f64 {
    if cycle_time > 0.0 {
        quantity * 86_400.0 / cycle_time
    } else {
        0.0
    }
}

fn rounded(value: f64) -> f64 {
    ((value + f64::EPSILON) * 1_000_000.0).round() / 1_000_000.0
}

fn row_for<'a>(
    aggregates: &'a mut BTreeMap<u64, Aggregate>,
    type_id: u64,
    name: &str,
) -> &'a mut Aggregate {
    let row = aggregates.entry(type_id).or_insert_with(|| Aggregate {
        type_id,
        name: name.to_string(),
        ..Aggregate::default()
    });
    if row.name.is_empty() && !name.is_empty() {
        row.name = name.to_string();
    }
    row
}

fn normalized_resource_name(name: &str) -> String {
    name.chars()
        .filter(|character| character.is_ascii_alphanumeric())
        .flat_map(char::to_lowercase)
        .collect()
}

fn planet_types_for(name: &str) -> &'static [&'static str] {
    match normalized_resource_name(name).as_str() {
        "aqueousliquids" => &["Barren", "Gas", "Ice", "Oceanic", "Storm", "Temperate"],
        "autotrophs" => &["Temperate"],
        "basemetals" => &["Barren", "Gas", "Lava", "Plasma", "Storm"],
        "carboncompounds" => &["Barren", "Oceanic", "Temperate"],
        "complexorganisms" => &["Oceanic", "Temperate"],
        "felsicmagma" => &["Lava"],
        "heavymetals" => &["Ice", "Lava", "Plasma"],
        "ionicsolutions" => &["Gas", "Storm"],
        "microorganisms" => &["Barren", "Ice", "Oceanic", "Temperate"],
        "noblegas" => &["Gas", "Ice", "Storm"],
        "noblemetals" => &["Barren", "Plasma"],
        "noncscrystals" => &["Lava", "Plasma"],
        "plankticcolonies" => &["Ice", "Oceanic"],
        "reactivegas" => &["Gas"],
        "suspendedplasma" => &["Lava", "Plasma", "Storm"],
        _ => &[],
    }
}

fn collect_dependency_type_ids(
    target_type_id: u64,
    recipes: &BTreeMap<u64, PlanetarySchematic>,
) -> BTreeSet<u64> {
    fn visit(
        type_id: u64,
        recipes: &BTreeMap<u64, PlanetarySchematic>,
        dependencies: &mut BTreeSet<u64>,
        visiting: &mut BTreeSet<u64>,
    ) {
        if !visiting.insert(type_id) {
            return;
        }
        if let Some(recipe) = recipes.get(&type_id) {
            for input in &recipe.inputs {
                dependencies.insert(input.type_id);
                visit(input.type_id, recipes, dependencies, visiting);
            }
        }
        visiting.remove(&type_id);
    }

    let mut dependencies = BTreeSet::new();
    visit(
        target_type_id,
        recipes,
        &mut dependencies,
        &mut BTreeSet::new(),
    );
    dependencies
}

fn base_components_for(
    type_id: u64,
    quantity_per_day: f64,
    recipes: &BTreeMap<u64, PlanetarySchematic>,
    names: &BTreeMap<u64, String>,
) -> Vec<BaseComponent> {
    fn expand(
        current_type_id: u64,
        quantity: f64,
        recipes: &BTreeMap<u64, PlanetarySchematic>,
        names: &BTreeMap<u64, String>,
        visiting: &mut BTreeSet<u64>,
        totals: &mut BTreeMap<u64, (String, f64, Vec<&'static str>)>,
    ) {
        if quantity <= 0.0 || !visiting.insert(current_type_id) {
            return;
        }

        if let Some(recipe) = recipes.get(&current_type_id) {
            if !recipe.inputs.is_empty() {
                for input in &recipe.inputs {
                    expand(
                        input.type_id,
                        quantity * input.quantity / recipe.output.quantity,
                        recipes,
                        names,
                        visiting,
                        totals,
                    );
                }
                visiting.remove(&current_type_id);
                return;
            }
        }

        let name = names
            .get(&current_type_id)
            .cloned()
            .or_else(|| recipes.get(&current_type_id).map(|recipe| recipe.output.name.clone()))
            .unwrap_or_else(|| format!("Type {current_type_id}"));
        let planet_types = planet_types_for(&name);
        if !planet_types.is_empty() {
            let entry = totals
                .entry(current_type_id)
                .or_insert_with(|| (name, 0.0, planet_types.to_vec()));
            entry.1 += quantity;
        }
        visiting.remove(&current_type_id);
    }

    let mut totals = BTreeMap::new();
    expand(
        type_id,
        quantity_per_day,
        recipes,
        names,
        &mut BTreeSet::new(),
        &mut totals,
    );
    let mut rows: Vec<BaseComponent> = totals
        .into_iter()
        .map(|(type_id, (name, quantity_per_day, planet_types))| BaseComponent {
            type_id,
            name,
            quantity_per_day: rounded(quantity_per_day),
            planet_types,
        })
        .collect();
    rows.sort_by(|left, right| {
        left.name
            .cmp(&right.name)
            .then_with(|| left.type_id.cmp(&right.type_id))
    });
    rows
}

fn severity_for(coverage: f64) -> &'static str {
    if coverage >= 1.0 {
        "covered"
    } else if coverage < 0.5 {
        "critical"
    } else if coverage < 0.75 {
        "short"
    } else {
        "watch"
    }
}

fn severity_order(severity: &str) -> u8 {
    match severity {
        "critical" => 0,
        "short" => 1,
        "watch" => 2,
        _ => 3,
    }
}

pub fn available_planetary_shortage_targets(
    data: &PlanetaryIndustryPayload,
) -> Vec<PlanetaryShortageTarget> {
    let mut targets: BTreeMap<u64, PlanetaryShortageTarget> = BTreeMap::new();
    for colony in &data.colonies {
        for pin in &colony.pins {
            let Some(schematic) = pin.schematic.as_ref().filter(|_| pin.is_factory) else {
                continue;
            };
            let output_per_day = per_day(schematic.output.quantity, schematic.cycle_time);
            let target = targets
                .entry(schematic.output.type_id)
                .or_insert_with(|| PlanetaryShortageTarget {
                    type_id: schematic.output.type_id,
                    name: schematic.output.name.clone(),
                    configured_factories: 0,
                    configured_output_per_day: 0.0,
                });
            target.configured_factories += 1;
            target.configured_output_per_day += output_per_day;
        }
    }
    let mut rows: Vec<PlanetaryShortageTarget> = targets
        .into_values()
        .map(|mut target| {
            target.configured_output_per_day = rounded(target.configured_output_per_day);
            target
        })
        .collect();
    rows.sort_by(|left, right| {
        left.name
            .cmp(&right.name)
            .then_with(|| left.type_id.cmp(&right.type_id))
    });
    rows
}

pub fn build_planetary_shortage_report(
    data: &PlanetaryIndustryPayload,
    target_type_id: Option<u64>,
    generated_at: &str,
) -> PlanetaryShortageReport {
    let mut aggregates: BTreeMap<u64, Aggregate> = BTreeMap::new();
    let mut recipes: BTreeMap<u64, PlanetarySchematic> = data
        .schematics
        .iter()
        .cloned()
        .map(|schematic| (schematic.output.type_id, schematic))
        .collect();

    for colony in &data.colonies {
        for pin in &colony.pins {
            for content in &pin.contents {
                row_for(&mut aggregates, content.type_id, &content.name).inventory += content.amount;
            }

            if let Some(extractor) = &pin.extractor {
                if let (Some(product_type_id), Some(product_name)) =
                    (extractor.product_type_id, extractor.product_name.as_deref())
                {
                    let aggregate = row_for(&mut aggregates, product_type_id, product_name);
                    aggregate.supply_per_day += extractor.projected_daily_output;
                    aggregate.producers += 1;
                    if pin.projected_status == "active" || pin.projected_status == "running" {
                        aggregate.running_producers += 1;
                    }
                }
            }

            let Some(pin_schematic) = pin.schematic.as_ref().filter(|_| pin.is_factory) else {
                continue;
            };
            recipes
                .entry(pin_schematic.output.type_id)
                .or_insert_with(|| pin_schematic.clone());
            let configured_schematic = recipes
                .get(&pin_schematic.output.type_id)
                .expect("configured schematic exists");
            let output_per_day = per_day(
                configured_schematic.output.quantity,
                configured_schematic.cycle_time,
            );
            let output = row_for(
                &mut aggregates,
                configured_schematic.output.type_id,
                &configured_schematic.output.name,
            );
            output.supply_per_day += output_per_day;
            output.producers += 1;
            output.producer_output_per_day = Some(output_per_day);
            if pin.projected_status == "running" {
                output.running_producers += 1;
            }
            if pin.projected_status == "starved" {
                output.starved_producers += 1;
            }

            for input in &configured_schematic.inputs {
                let aggregate = row_for(&mut aggregates, input.type_id, &input.name);
                aggregate.demand_per_day += per_day(input.quantity, configured_schematic.cycle_time);
                aggregate.consumers += 1;
            }
        }
    }

    for recipe in recipes.values() {
        if let Some(aggregate) = aggregates.get_mut(&recipe.output.type_id) {
            if aggregate.producer_output_per_day.is_none() {
                aggregate.producer_output_per_day = Some(per_day(
                    recipe.output.quantity,
                    recipe.cycle_time,
                ));
            }
        }
    }

    let targets = available_planetary_shortage_targets(data);
    let target = target_type_id.and_then(|type_id| {
        targets
            .iter()
            .find(|target| target.type_id == type_id)
            .cloned()
    });
    let included_type_ids: BTreeSet<u64> = match target_type_id {
        Some(type_id) => collect_dependency_type_ids(type_id, &recipes),
        None => aggregates
            .values()
            .filter(|aggregate| aggregate.demand_per_day > 0.0)
            .map(|aggregate| aggregate.type_id)
            .collect(),
    };
    let mut names: BTreeMap<u64, String> = aggregates
        .values()
        .map(|aggregate| (aggregate.type_id, aggregate.name.clone()))
        .collect();
    for recipe in recipes.values() {
        names.insert(recipe.output.type_id, recipe.output.name.clone());
        for input in &recipe.inputs {
            names.insert(input.type_id, input.name.clone());
        }
    }

    let mut commodities = Vec::new();
    for type_id in included_type_ids {
        let Some(aggregate) = aggregates.get(&type_id) else {
            continue;
        };
        if aggregate.demand_per_day <= 0.0 {
            continue;
        }
        let coverage = aggregate.supply_per_day / aggregate.demand_per_day;
        let net_shortfall = (aggregate.demand_per_day - aggregate.supply_per_day).max(0.0);
        let processor_gap = if net_shortfall <= 0.0 {
            Some(0)
        } else {
            aggregate
                .producer_output_per_day
                .filter(|value| *value > 0.0)
                .map(|value| (net_shortfall / value).ceil() as u64)
        };
        commodities.push(PlanetaryShortageRow {
            type_id: aggregate.type_id,
            name: aggregate.name.clone(),
            projected_inventory: rounded(aggregate.inventory),
            configured_supply_per_day: rounded(aggregate.supply_per_day),
            configured_demand_per_day: rounded(aggregate.demand_per_day),
            net_shortfall_per_day: rounded(net_shortfall),
            coverage: Some(rounded(coverage)),
            inventory_days_at_demand: Some(rounded(
                aggregate.inventory / aggregate.demand_per_day,
            )),
            runway_days_at_net_shortfall: if net_shortfall > 0.0 {
                Some(rounded(aggregate.inventory / net_shortfall))
            } else {
                None
            },
            configured_producers: aggregate.producers,
            configured_consumers: aggregate.consumers,
            running_producers: aggregate.running_producers,
            starved_producers: aggregate.starved_producers,
            producer_output_per_day: aggregate.producer_output_per_day.map(rounded),
            additional_processors_to_balance: processor_gap,
            base_components: base_components_for(type_id, net_shortfall, &recipes, &names),
            severity: severity_for(coverage),
        });
    }

    commodities.sort_by(|left, right| {
        severity_order(left.severity)
            .cmp(&severity_order(right.severity))
            .then_with(|| {
                left.coverage
                    .partial_cmp(&right.coverage)
                    .unwrap_or(Ordering::Equal)
            })
            .then_with(|| left.name.cmp(&right.name))
            .then_with(|| left.type_id.cmp(&right.type_id))
    });

    let summary = PlanetaryShortageSummary {
        critical_shortages: commodities
            .iter()
            .filter(|row| row.severity == "critical")
            .count(),
        shortages: commodities
            .iter()
            .filter(|row| row.severity == "short")
            .count(),
        watch_items: commodities
            .iter()
            .filter(|row| row.severity == "watch")
            .count(),
        covered_items: commodities
            .iter()
            .filter(|row| row.severity == "covered")
            .count(),
    };
    let scope = PlanetaryShortageScope {
        target_type_id: target.as_ref().map(|target| target.type_id),
        target_name: target.as_ref().map(|target| target.name.clone()),
        configured_target_factories: target
            .as_ref()
            .map(|target| target.configured_factories)
            .unwrap_or(0),
        configured_target_output_per_day: target
            .as_ref()
            .map(|target| target.configured_output_per_day)
            .unwrap_or(0.0),
        commodity_count: commodities.len(),
    };

    PlanetaryShortageReport {
        schema_version: PLANETARY_SHORTAGE_REPORT_SCHEMA,
        generated_at: generated_at.to_string(),
        source_as_of: data.as_of.clone(),
        methodology: "configured-throughput-with-projected-inventory",
        scope,
        summary,
        commodities,
        caveats: vec![
            "Configured throughput counts every configured factory at full-cycle capacity, including idle or not-yet-started factories.",
            "Projected inventory is network-wide and may be stranded on another character or planet until hauled.",
            "Manual transfers, expedited routes, and unsubmitted colony edits remain unknown until ESI publishes a newer checkpoint.",
            "Additional processor counts are throughput equivalents and do not validate a planet's CPU or powergrid fit.",
            "Planet types show where a raw resource can occur, not the density or quality of a specific planet.",
        ],
    }
}
