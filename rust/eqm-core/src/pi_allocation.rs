//! Bounded PI colony packing over a frozen, authorized backend snapshot.
//! No market/network access. One worker holds the catalog for the whole search,
//! avoiding a process launch and repeated catalog serialization per candidate.
use serde::Deserialize;
use serde_json::{json, Value};
use std::collections::{BTreeMap, HashSet};
use std::io::{BufRead, Write};
use std::time::{Duration, Instant};

const WEEK: f64 = 168.0;
const CC_UPGRADE: [f64; 6] = [0., 580000., 1510000., 2710000., 4210000., 6310000.];
fn batches(q: f64, size: f64) -> f64 {
    (q / size - 1e-9).ceil().max(0.)
}

#[derive(Clone, Deserialize)]
pub struct Part {
    type_id: u64,
    quantity: f64,
}
#[derive(Clone, Deserialize)]
pub struct Recipe {
    id: u64,
    cycle_time: f64,
    inputs: Vec<Part>,
    output: Part,
}
#[derive(Clone, Deserialize)]
pub struct Commodity {
    name: String,
    tier: u8,
    volume: f64,
    tax_base: f64,
    planet_types: Vec<String>,
    recipe: Option<Recipe>,
}
#[derive(Clone, Deserialize)]
pub struct Pin {
    name: String,
    price: f64,
    capacity: f64,
    dogma: BTreeMap<String, f64>,
}
#[derive(Clone, Deserialize)]
pub struct Yield {
    type_id: u64,
    units_per_head_hour: f64,
    source: String,
}
#[derive(Clone, Deserialize)]
pub struct Planet {
    key: String,
    name: String,
    planet_type: String,
    planet_id: Option<u64>,
    #[serde(default)]
    system_id: Option<u64>,
    diameter_km: f64,
    security: f64,
    customs_percent: f64,
    npc_tax_percent: f64,
    yields: Vec<Yield>,
}
#[derive(Clone, Deserialize)]
pub struct Existing {
    id: u64,
    upgrade_level: usize,
}
#[derive(Clone, Deserialize)]
pub struct Slot {
    character_id: u64,
    name: String,
    ccu: usize,
    cce: f64,
    cpu: f64,
    power: f64,
    available: usize,
    planets: Vec<Planet>,
    released: BTreeMap<u64, Existing>,
}
#[derive(Clone, Deserialize)]
pub struct Schedule {
    visits_per_week: f64,
    program_hours: f64,
    restart_minutes: f64,
    link_length_km: f64,
}
#[derive(Clone, Deserialize)]
pub struct Costs {
    additional_setup_per_colony: f64,
}
#[derive(Clone, Deserialize)]
pub struct State {
    pub schema_version: String,
    catalog: BTreeMap<u64, Commodity>,
    pins: BTreeMap<u64, Pin>,
    schedule: Schedule,
    costs: Costs,
    slots: Vec<Slot>,
    notes: Vec<String>,
}
#[derive(Clone, Deserialize)]
pub struct Node {
    type_id: u64,
    batches: f64,
}
#[derive(Clone, Deserialize)]
pub struct Candidate {
    nodes: BTreeMap<u64, Node>,
    raw: BTreeMap<u64, f64>,
    time_limit_ms: u64,
}

#[derive(Clone)]
struct Facility {
    kind: String,
    type_id: u64,
    pin: Pin,
    count: usize,
    heads: usize,
    product: Option<u64>,
    schematic: Option<u64>,
    source: Option<String>,
}
impl Facility {
    fn attr(&self, id: &str, default: f64) -> f64 {
        *self.pin.dogma.get(id).unwrap_or(&default)
    }
    fn cpu(&self) -> f64 {
        self.attr("49", 0.) * self.count as f64 + self.heads as f64 * self.attr("1690", 110.)
    }
    fn power(&self) -> f64 {
        self.attr("15", 0.) * self.count as f64 + self.heads as f64 * self.attr("1691", 550.)
    }
    fn value(&self) -> Value {
        let mut v = json!({"kind":self.kind,"type_id":self.type_id,"name":self.pin.name,"cpu":self.attr("49",0.),"power":self.attr("15",0.),"price":self.pin.price,"capacity":self.pin.capacity,"head_cpu":self.attr("1690",110.),"head_power":self.attr("1691",550.),"count":self.count});
        if let Some(t) = self.product {
            v["product_type_id"] = json!(t);
        }
        if let Some(s) = self.schematic {
            v["schematic_id"] = json!(s);
        }
        if let Some(ref source) = self.source {
            v["yield_source"] = json!(source);
            v["heads"] = json!(self.heads);
        }
        v
    }
}

impl State {
    pub fn validate(&self) -> Result<(), String> {
        if self.schema_version != "eqm.pi-allocation-state.v1"
            || self.catalog.len() > 83
            || self.pins.len() > 200
            || self.slots.len() > 12
        {
            return Err("Invalid PI allocation state version or size".into());
        }
        if !(1. ..=168.).contains(&self.schedule.visits_per_week)
            || !(1. ..=336.).contains(&self.schedule.program_hours)
            || !(0. ..=1440.).contains(&self.schedule.restart_minutes)
            || !(1. ..=10000.).contains(&self.schedule.link_length_km)
        {
            return Err("Invalid PI allocation schedule".into());
        }
        for item in self.catalog.values() {
            if item.volume <= 0.
                || item.tier > 4
                || item.recipe.as_ref().is_some_and(|r| {
                    r.cycle_time <= 0.
                        || r.output.quantity <= 0.
                        || r.inputs.is_empty()
                        || r.inputs
                            .iter()
                            .any(|i| i.quantity <= 0. || !self.catalog.contains_key(&i.type_id))
                })
            {
                return Err("Invalid PI commodity or recipe".into());
            }
        }
        for slot in &self.slots {
            if slot.ccu > 5
                || slot.available > 6
                || slot.planets.len() > 60
                || slot.cpu < 0.
                || slot.power < 0.
                || !(0. ..=5.).contains(&slot.cce)
            {
                return Err("Invalid PI pilot limits".into());
            }
            if slot.planets.iter().any(|p| {
                p.yields
                    .iter()
                    .any(|y| y.units_per_head_hour <= 0. || y.units_per_head_hour > 1e7)
            }) {
                return Err("Invalid PI extraction yield".into());
            }
        }
        Ok(())
    }
    fn facility(&self, kind: &str, planet: &str, count: usize) -> Result<Facility, String> {
        let suffix = match kind {
            "basic" => "Basic Industry Facility",
            "advanced" => "Advanced Industry Facility",
            "hightech" => "High-Tech Production Plant",
            "ecu" => "Extractor Control Unit",
            "storage" => "Storage Facility",
            "launchpad" => "Launchpad",
            "command" => "Command Center",
            _ => return Err("Unknown facility".into()),
        };
        let name = format!("{planet} {suffix}");
        let (id, pin) = self
            .pins
            .iter()
            .find(|(_, p)| p.name == name)
            .ok_or_else(|| format!("Missing PI facility {name}"))?;
        Ok(Facility {
            kind: kind.into(),
            type_id: *id,
            pin: pin.clone(),
            count,
            heads: 0,
            product: None,
            schematic: None,
            source: None,
        })
    }
    fn layout(
        &self,
        type_id: u64,
        runs: f64,
        processors: usize,
        planet: &Planet,
        pilot: &Slot,
        extraction: bool,
        detailed: bool,
    ) -> Result<Option<Value>, String> {
        let item = &self.catalog[&type_id];
        let recipe = item
            .recipe
            .as_ref()
            .ok_or("Raw commodity cannot be a factory target")?;
        let kind = match item.tier {
            1 => "basic",
            4 => "hightech",
            _ => "advanced",
        };
        if kind == "hightech" && planet.planet_type != "Barren" && planet.planet_type != "Temperate"
        {
            return Ok(None);
        }
        let mut factory = self.facility(kind, &planet.planet_type, processors)?;
        factory.schematic = Some(recipe.id);
        factory.product = Some(type_id);
        let pad = self.facility("launchpad", &planet.planet_type, 1)?;
        let mut storage = self.facility("storage", &planet.planet_type, 1)?;
        if pad.pin.capacity <= 0. || storage.pin.capacity <= 0. {
            return Err("Missing storage capacity".into());
        }
        let inputs: BTreeMap<u64, f64> = recipe
            .inputs
            .iter()
            .map(|i| (i.type_id, i.quantity * runs))
            .collect();
        let outputs = BTreeMap::from([(type_id, recipe.output.quantity * runs)]);
        let mut facilities = vec![factory, pad.clone()];
        let mut heads = 0usize;
        let mut raw_output = BTreeMap::new();
        let mut raw_buffer = 0.;
        if extraction {
            if inputs.len() != 1 {
                return Ok(None);
            }
            let (&raw_id, &need) = inputs.iter().next().unwrap();
            let Some(estimate) = planet.yields.iter().find(|e| e.type_id == raw_id) else {
                return Ok(None);
            };
            if !self.catalog[&raw_id]
                .planet_types
                .contains(&planet.planet_type)
            {
                return Ok(None);
            }
            let interval = WEEK / self.schedule.visits_per_week;
            let uptime = self
                .schedule
                .program_hours
                .min((interval - self.schedule.restart_minutes / 60.).max(0.));
            let weekly = estimate.units_per_head_hour * uptime * self.schedule.visits_per_week;
            if weekly <= 0. {
                return Ok(None);
            }
            heads = batches(need, weekly) as usize;
            if heads > 10 {
                return Ok(None);
            }
            let mut ecu = self.facility("ecu", &planet.planet_type, 1)?;
            ecu.heads = heads;
            ecu.product = Some(raw_id);
            ecu.source = Some(estimate.source.clone());
            facilities.push(ecu);
            raw_output.insert(raw_id, need);
            raw_buffer = need.min(estimate.units_per_head_hour * heads as f64 * 4.)
                * self.catalog[&raw_id].volume;
        }
        let external = if extraction {
            BTreeMap::new()
        } else {
            inputs.clone()
        };
        let volume = |map: &BTreeMap<u64, f64>| {
            map.iter()
                .map(|(t, q)| q * self.catalog[t].volume)
                .sum::<f64>()
        };
        let incoming = volume(&external);
        let outgoing = volume(&outputs);
        let required_storage = (incoming + outgoing) / self.schedule.visits_per_week + raw_buffer;
        let stores = batches(
            (required_storage - pad.pin.capacity).max(0.),
            storage.pin.capacity,
        ) as usize;
        if stores > 30 {
            return Ok(None);
        }
        let capacity = pad.pin.capacity + stores as f64 * storage.pin.capacity;
        if stores > 0 {
            storage.count = stores;
            facilities.push(storage);
        }
        let mut flows = vec![(volume(&inputs) + outgoing) / processors as f64 / WEEK; processors];
        if heads > 0 {
            flows.push(volume(&raw_output) / WEEK * 2.);
        }
        flows.extend(vec![
            (incoming + outgoing + raw_buffer)
                / stores.max(1) as f64
                / WEEK;
            stores
        ]);
        let levels: Vec<f64> = flows
            .iter()
            .map(|f| (f / 1250.).max(1.).log2().ceil().max(0.))
            .collect();
        if levels.iter().any(|l| *l > 10.) {
            return Ok(None);
        }
        let length = self.schedule.link_length_km;
        let cpu = facilities.iter().map(Facility::cpu).sum::<f64>()
            + levels
                .iter()
                .map(|l| (15. + 0.2 * length) * 1.4_f64.powf(*l))
                .sum::<f64>();
        let power = facilities.iter().map(Facility::power).sum::<f64>()
            + levels
                .iter()
                .map(|l| (10. + 0.15 * length) * 1.2_f64.powf(*l))
                .sum::<f64>();
        if cpu > pilot.cpu || power > pilot.power {
            return Ok(None);
        }
        let old = planet.planet_id.and_then(|id| pilot.released.get(&id));
        let command_price = if let Some(old) = old {
            (CC_UPGRADE[pilot.ccu] - CC_UPGRADE[old.upgrade_level.min(5)]).max(0.)
        } else {
            self.facility("command", &planet.planet_type, 1)?.pin.price + CC_UPGRADE[pilot.ccu]
        };
        let setup = facilities
            .iter()
            .map(|f| f.pin.price * f.count as f64)
            .sum::<f64>()
            + command_price
            + self.costs.additional_setup_per_colony;
        let rate = planet.customs_percent / 100.
            + if planet.security >= 0.5 {
                planet.npc_tax_percent / 100. * (1. - 0.1 * pilot.cce)
            } else {
                0.
            };
        let customs = rate
            * (external
                .iter()
                .map(|(t, q)| q * self.catalog[t].tax_base * 0.5)
                .sum::<f64>()
                + outputs
                    .iter()
                    .map(|(t, q)| q * self.catalog[t].tax_base)
                    .sum::<f64>());
        if !detailed {
            return Ok(Some(json!({"customs_isk": customs, "setup_isk": setup})));
        }
        let planet_json = json!({"key":planet.key,"name":planet.name,"planet_type":planet.planet_type,"planet_id":planet.planet_id,"system_id":planet.system_id,"diameter_km":planet.diameter_km,"security":planet.security,"customs_percent":planet.customs_percent,"npc_tax_percent":planet.npc_tax_percent,"yields":planet.yields.iter().map(|y|json!({"type_id":y.type_id,"units_per_head_hour":y.units_per_head_hour,"source":y.source})).collect::<Vec<_>>()});
        Ok(Some(
            json!({"character_id":pilot.character_id,"character_name":pilot.name,"planet_key":planet.key,"planet":planet_json,"replaces_colony_id":old.map(|o|o.id),"ccu":pilot.ccu,"product_type_id":type_id,"processors":processors,"batches":runs,"heads":heads,"facilities":facilities.iter().map(Facility::value).collect::<Vec<_>>(),"inputs":inputs,"external_inputs":external,"outputs":outputs,"extraction":raw_output,"cpu":cpu,"power":power,"cpu_limit":pilot.cpu,"power_limit":pilot.power,"storage_required_m3":required_storage,"storage_m3":capacity,"link_levels":levels,"link_length_km":length,"setup_isk":setup,"customs_isk":customs,"customs_rate":rate,"haul_m3":incoming+outgoing,"weekly_factory_utilization":runs*recipe.cycle_time/(processors as f64*604800.)}),
        ))
    }

    pub fn allocate(&self, candidate: Candidate) -> Result<Value, String> {
        if candidate.nodes.len() > 68
            || candidate.raw.len() > 15
            || candidate.nodes.values().any(|n| {
                n.batches <= 0. || n.batches > 1e12 || !self.catalog.contains_key(&n.type_id)
            })
        {
            return Err("Invalid PI candidate size or node".into());
        }
        let deadline = Instant::now() + Duration::from_millis(candidate.time_limit_ms.min(30000));
        let mut nodes: Vec<_> = candidate.nodes.values().collect();
        nodes.sort_by_key(|n| (std::cmp::Reverse(self.catalog[&n.type_id].tier), n.type_id));
        let mut available: Vec<_> = self.slots.iter().map(|s| s.available).collect();
        let mut used: Vec<HashSet<String>> = vec![HashSet::new(); self.slots.len()];
        let mut colonies = Vec::new();
        for node in nodes {
            let item = &self.catalog[&node.type_id];
            let recipe = item.recipe.as_ref().ok_or("Missing factory recipe")?;
            let per_factory = (604800. / recipe.cycle_time).floor();
            if per_factory < 1. {
                return Err("Schematic exceeds weekly horizon".into());
            }
            let extraction = item.tier == 1
                && recipe
                    .inputs
                    .iter()
                    .any(|i| candidate.raw.contains_key(&i.type_id));
            let mut remaining = node.batches;
            while remaining > 0. {
                let mut best: Option<(f64, f64, f64, usize, String, usize)> = None;
                for (index, pilot) in self.slots.iter().enumerate() {
                    if available[index] == 0 {
                        continue;
                    }
                    for (planet_index, planet) in pilot.planets.iter().enumerate() {
                        if Instant::now() >= deadline {
                            return Ok(json!({"colonies":null,"notes":["Search cancelled"]}));
                        }
                        let identity = planet
                            .planet_id
                            .map(|id| format!("planet:{id}"))
                            .unwrap_or_else(|| format!("key:{}", planet.key));
                        if used[index].contains(&identity) {
                            continue;
                        }
                        for processors in
                            (1..=32.min(batches(remaining, per_factory) as usize)).rev()
                        {
                            let runs = remaining.min(processors as f64 * per_factory);
                            if let Some(row) = self.layout(
                                node.type_id,
                                runs,
                                processors,
                                planet,
                                pilot,
                                extraction,
                                false,
                            )? {
                                let customs = -row["customs_isk"].as_f64().unwrap();
                                let setup = -row["setup_isk"].as_f64().unwrap();
                                if best
                                    .as_ref()
                                    .is_none_or(|b| (runs, customs, setup) > (b.0, b.1, b.2))
                                {
                                    best = Some((
                                        runs,
                                        customs,
                                        setup,
                                        index,
                                        identity.clone(),
                                        planet_index,
                                    ));
                                }
                                break;
                            }
                        }
                    }
                }
                let Some((runs, _, _, index, identity, planet_index)) = best else {
                    let mut notes = self.notes.clone();
                    notes.push(format!("No remaining colony can fit {} with these skills, yields and visit/storage limits",item.name));
                    return Ok(json!({"colonies":null,"notes":notes}));
                };
                let pilot = &self.slots[index];
                let processors = batches(runs, per_factory) as usize;
                let row = self
                    .layout(
                        node.type_id,
                        runs,
                        processors,
                        &pilot.planets[planet_index],
                        pilot,
                        extraction,
                        true,
                    )?
                    .ok_or("Selected allocation no longer fits")?;
                available[index] -= 1;
                used[index].insert(identity);
                colonies.push(row);
                remaining -= runs;
            }
        }
        Ok(json!({"colonies":colonies,"notes":self.notes}))
    }
}

/// Newline-delimited protocol: immutable state, then candidate messages. EOF closes.
pub fn serve() -> Result<(), String> {
    let stdin = std::io::stdin();
    let mut reader = stdin.lock();
    let stdout = std::io::stdout();
    let mut writer = stdout.lock();
    let read_line = |reader: &mut std::io::StdinLock<'_>| -> Result<Option<String>, String> {
        let mut bytes = Vec::new();
        std::io::Read::take(reader, 8 * 1024 * 1024 + 1)
            .read_until(b'\n', &mut bytes)
            .map_err(|e| e.to_string())?;
        if bytes.len() > 8 * 1024 * 1024 {
            return Err("PI worker message exceeds 8 MB".into());
        }
        if bytes.is_empty() {
            return Ok(None);
        }
        String::from_utf8(bytes)
            .map(Some)
            .map_err(|e| e.to_string())
    };
    let state: State = serde_json::from_str(&read_line(&mut reader)?.ok_or("Missing PI state")?)
        .map_err(|e| e.to_string())?;
    state.validate()?;
    writeln!(writer, "{{\"ready\":true}}")
        .and_then(|_| writer.flush())
        .map_err(|e| e.to_string())?;
    while let Some(line) = read_line(&mut reader)? {
        let candidate: Candidate = serde_json::from_str(&line).map_err(|e| e.to_string())?;
        let result = state.allocate(candidate)?;
        writeln!(writer, "{}", result)
            .and_then(|_| writer.flush())
            .map_err(|e| e.to_string())?;
    }
    Ok(())
}
