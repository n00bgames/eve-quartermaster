use std::{
    cmp::Reverse,
    collections::{BTreeMap, BTreeSet, BinaryHeap},
};

use chrono::{DateTime, Duration, SecondsFormat, Utc};
use serde::{Deserialize, Serialize};

pub const MAX_SIMULATION_EVENTS: usize = 100_000;

fn default_max_events() -> usize {
    MAX_SIMULATION_EVENTS
}

fn default_decay_factor() -> f64 {
    0.012
}

fn default_noise_factor() -> f64 {
    0.8
}

#[derive(Clone, Debug, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum PinKind {
    Extractor,
    Factory,
    Storage,
    Infrastructure,
}

#[derive(Clone, Debug, Deserialize)]
pub struct SimulationSchematic {
    pub cycle_time: i64,
    #[serde(default)]
    pub inputs: BTreeMap<i64, i64>,
    pub output_type_id: i64,
    pub output_quantity: i64,
}

#[derive(Clone, Debug, Deserialize)]
pub struct SimulationRoute {
    pub source_pin_id: i64,
    pub destination_pin_id: i64,
    pub content_type_id: i64,
    pub quantity: i64,
}

#[derive(Clone, Debug, Deserialize)]
pub struct SimulationPin {
    pub pin_id: i64,
    pub kind: PinKind,
    #[serde(default)]
    pub contents: BTreeMap<i64, i64>,
    pub capacity_m3: Option<f64>,
    pub schematic: Option<SimulationSchematic>,
    pub last_cycle_start: Option<DateTime<Utc>>,
    pub install_time: Option<DateTime<Utc>>,
    pub expiry_time: Option<DateTime<Utc>>,
    pub extractor_cycle_time: Option<i64>,
    pub extractor_product_type_id: Option<i64>,
    pub extractor_quantity_per_cycle: Option<i64>,
    #[serde(default = "default_decay_factor")]
    pub extractor_decay_factor: f64,
    #[serde(default = "default_noise_factor")]
    pub extractor_noise_factor: f64,
}

#[derive(Clone, Debug, Deserialize)]
pub struct ColonySimulationInput {
    pub schema_version: String,
    pub checkpoint_at: Option<DateTime<Utc>>,
    pub projected_at: DateTime<Utc>,
    #[serde(default = "default_max_events")]
    pub max_events: usize,
    pub pins: Vec<SimulationPin>,
    #[serde(default)]
    pub routes: Vec<SimulationRoute>,
    #[serde(default)]
    pub type_volumes: BTreeMap<i64, f64>,
}

#[derive(Clone, Debug, Serialize, PartialEq, Eq)]
pub struct PinSimulationResult {
    pub contents: BTreeMap<i64, i64>,
    pub status: String,
    pub produced: BTreeMap<i64, i64>,
    pub blocked: BTreeMap<i64, i64>,
}

#[derive(Clone, Debug, Serialize, PartialEq, Eq)]
pub struct ColonySimulationResult {
    pub checkpoint_at: Option<String>,
    pub projected_at: String,
    pub is_projection: bool,
    pub events_processed: usize,
    pub truncated: bool,
    pub pins: BTreeMap<i64, PinSimulationResult>,
}

#[derive(Clone, Debug)]
struct PinState {
    definition: SimulationPin,
    contents: BTreeMap<i64, i64>,
    factory_running_until: Option<DateTime<Utc>>,
    status: String,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
enum EventKind {
    Extractor,
    Factory,
}

type Event = (DateTime<Utc>, u64, EventKind, i64);

struct Simulator {
    checkpoint: DateTime<Utc>,
    target: DateTime<Utc>,
    pin_order: Vec<i64>,
    states: BTreeMap<i64, PinState>,
    outgoing: BTreeMap<(i64, i64), Vec<SimulationRoute>>,
    incoming: BTreeMap<(i64, i64), Vec<SimulationRoute>>,
    type_volumes: BTreeMap<i64, f64>,
    events: BinaryHeap<Reverse<Event>>,
    next_event_order: u64,
    produced: BTreeMap<i64, BTreeMap<i64, i64>>,
    blocked: BTreeMap<i64, BTreeMap<i64, i64>>,
}

pub fn known_pin_capacity_m3(type_name: &str) -> Option<f64> {
    let name = type_name.to_lowercase();
    if name.contains("launchpad") {
        Some(10_000.0)
    } else if name.contains("storage") {
        Some(12_000.0)
    } else if name.contains("command center") {
        Some(500.0)
    } else {
        None
    }
}

pub fn extractor_cycle_output(
    cycle_index: i64,
    cycle_time: i64,
    quantity_per_cycle: i64,
    decay_factor: f64,
    noise_factor: f64,
) -> i64 {
    if cycle_index < 0 || cycle_time <= 0 || quantity_per_cycle <= 0 {
        return 0;
    }
    let bar_width = cycle_time as f64 / 900.0;
    let time_value = (cycle_index as f64 + 0.5) * bar_width;
    let decay_value = quantity_per_cycle as f64 / (1.0 + time_value * decay_factor);
    let phase_shift = (quantity_per_cycle as f64).powf(0.7);
    let waves = ((phase_shift + time_value / 12.0).cos()
        + (phase_shift / 2.0 + time_value * 0.2).cos()
        + (time_value * 0.5).cos())
        / 3.0;
    let bar_height = decay_value * (1.0 + noise_factor * waves.max(0.0));
    (bar_width * bar_height).floor().max(0.0) as i64
}

fn iso(value: DateTime<Utc>) -> String {
    value.to_rfc3339_opts(SecondsFormat::AutoSi, true)
}

pub fn simulate_colony(input: ColonySimulationInput) -> Result<ColonySimulationResult, String> {
    if input.schema_version != "eqm.planetary-colony-simulation-input.v1" {
        return Err(format!(
            "unsupported colony simulation schema: {}",
            input.schema_version
        ));
    }
    let target = input.projected_at;
    let pin_order = input.pins.iter().map(|pin| pin.pin_id).collect::<Vec<_>>();
    let states = input
        .pins
        .into_iter()
        .map(|pin| {
            let contents = pin
                .contents
                .iter()
                .map(|(type_id, quantity)| (*type_id, (*quantity).max(0)))
                .collect();
            (
                pin.pin_id,
                PinState {
                    definition: pin,
                    contents,
                    factory_running_until: None,
                    status: "online".to_string(),
                },
            )
        })
        .collect::<BTreeMap<_, _>>();

    let Some(checkpoint) = input.checkpoint_at else {
        return Ok(build_result(
            states,
            None,
            target,
            0,
            false,
            false,
            BTreeMap::new(),
            BTreeMap::new(),
        ));
    };
    if target <= checkpoint {
        return Ok(build_result(
            states,
            Some(checkpoint),
            target,
            0,
            false,
            false,
            BTreeMap::new(),
            BTreeMap::new(),
        ));
    }

    let mut outgoing: BTreeMap<(i64, i64), Vec<SimulationRoute>> = BTreeMap::new();
    let mut incoming: BTreeMap<(i64, i64), Vec<SimulationRoute>> = BTreeMap::new();
    for route in input.routes {
        outgoing
            .entry((route.source_pin_id, route.content_type_id))
            .or_default()
            .push(route.clone());
        incoming
            .entry((route.destination_pin_id, route.content_type_id))
            .or_default()
            .push(route);
    }
    for routes in outgoing.values_mut().chain(incoming.values_mut()) {
        routes.sort_by_key(|route| (route.destination_pin_id, route.source_pin_id));
    }

    let mut simulator = Simulator {
        checkpoint,
        target,
        pin_order,
        states,
        outgoing,
        incoming,
        type_volumes: input.type_volumes,
        events: BinaryHeap::new(),
        next_event_order: 0,
        produced: BTreeMap::new(),
        blocked: BTreeMap::new(),
    };
    simulator.initialize();
    let (events_processed, truncated) = simulator.run(input.max_events);
    simulator.finalize();
    Ok(build_result(
        simulator.states,
        Some(checkpoint),
        target,
        events_processed,
        true,
        truncated,
        simulator.produced,
        simulator.blocked,
    ))
}

impl Simulator {
    fn schedule(&mut self, when: DateTime<Utc>, kind: EventKind, pin_id: i64) {
        if when <= self.target {
            self.events
                .push(Reverse((when, self.next_event_order, kind, pin_id)));
            self.next_event_order += 1;
        }
    }

    fn capacity_remaining(&self, pin_id: i64) -> Option<f64> {
        let state = self.states.get(&pin_id)?;
        let capacity = state.definition.capacity_m3?;
        let used = state
            .contents
            .iter()
            .map(|(type_id, quantity)| {
                self.type_volumes.get(type_id).copied().unwrap_or(0.0) * *quantity as f64
            })
            .sum::<f64>();
        Some((capacity - used).max(0.0))
    }

    fn add_commodity(&mut self, pin_id: i64, type_id: i64, quantity: i64) -> i64 {
        if quantity <= 0 || !self.states.contains_key(&pin_id) {
            return 0;
        }
        let remaining = self.capacity_remaining(pin_id);
        let volume = self
            .type_volumes
            .get(&type_id)
            .copied()
            .unwrap_or(0.0)
            .max(0.0);
        let accepted = if let Some(remaining) = remaining.filter(|_| volume > 0.0) {
            quantity.min((remaining / volume).floor() as i64)
        } else {
            quantity
        };
        if accepted > 0 {
            *self
                .states
                .get_mut(&pin_id)
                .unwrap()
                .contents
                .entry(type_id)
                .or_default() += accepted;
        }
        accepted
    }

    fn remove_commodity(&mut self, pin_id: i64, type_id: i64, quantity: i64) -> i64 {
        let Some(state) = self.states.get_mut(&pin_id) else {
            return 0;
        };
        let available = state.contents.get(&type_id).copied().unwrap_or(0);
        let removed = quantity.max(0).min(available);
        if removed > 0 {
            let remaining = available - removed;
            if remaining > 0 {
                state.contents.insert(type_id, remaining);
            } else {
                state.contents.remove(&type_id);
            }
        }
        removed
    }

    fn route_output(
        &mut self,
        source_pin_id: i64,
        type_id: i64,
        quantity: i64,
        when: DateTime<Utc>,
    ) -> bool {
        let mut remaining = quantity;
        let mut destinations = BTreeSet::new();
        let routes = self
            .outgoing
            .get(&(source_pin_id, type_id))
            .cloned()
            .unwrap_or_default();
        for route in routes {
            if remaining <= 0 || !self.states.contains_key(&route.destination_pin_id) {
                continue;
            }
            let moved = self.add_commodity(
                route.destination_pin_id,
                type_id,
                remaining.min(route.quantity.max(0)),
            );
            remaining -= moved;
            destinations.insert(route.destination_pin_id);
        }
        if remaining > 0 {
            *self
                .blocked
                .entry(source_pin_id)
                .or_default()
                .entry(type_id)
                .or_default() += remaining;
        }
        for destination_id in destinations {
            let should_start = self
                .states
                .get(&destination_id)
                .map(|state| {
                    state.definition.kind == PinKind::Factory
                        && state.factory_running_until.is_none()
                })
                .unwrap_or(false);
            if should_start {
                self.try_start_factory(destination_id, when);
            }
        }
        remaining == 0
    }

    fn pull_factory_inputs(&mut self, pin_id: i64) {
        let Some(schematic) = self
            .states
            .get(&pin_id)
            .and_then(|state| state.definition.schematic.clone())
        else {
            return;
        };
        for (type_id, required) in schematic.inputs {
            let current = self
                .states
                .get(&pin_id)
                .and_then(|state| state.contents.get(&type_id))
                .copied()
                .unwrap_or(0);
            let mut needed = (required - current).max(0);
            let routes = self
                .incoming
                .get(&(pin_id, type_id))
                .cloned()
                .unwrap_or_default();
            for route in routes {
                if needed <= 0 {
                    break;
                }
                let moved = self.remove_commodity(
                    route.source_pin_id,
                    type_id,
                    needed.min(route.quantity.max(0)),
                );
                if moved > 0 {
                    self.add_commodity(pin_id, type_id, moved);
                    needed -= moved;
                }
            }
        }
    }

    fn try_start_factory(&mut self, pin_id: i64, when: DateTime<Utc>) -> bool {
        let Some(schematic) = self
            .states
            .get(&pin_id)
            .and_then(|state| state.definition.schematic.clone())
        else {
            return false;
        };
        if schematic.cycle_time <= 0
            || self
                .states
                .get(&pin_id)
                .and_then(|state| state.factory_running_until)
                .is_some()
        {
            return false;
        }
        self.pull_factory_inputs(pin_id);
        let has_inputs = schematic.inputs.iter().all(|(type_id, required)| {
            self.states
                .get(&pin_id)
                .and_then(|state| state.contents.get(type_id))
                .copied()
                .unwrap_or(0)
                >= *required
        });
        if !has_inputs {
            self.states.get_mut(&pin_id).unwrap().status = "starved".to_string();
            return false;
        }
        for (type_id, required) in &schematic.inputs {
            self.remove_commodity(pin_id, *type_id, *required);
        }
        let completion = when + Duration::seconds(schematic.cycle_time);
        let state = self.states.get_mut(&pin_id).unwrap();
        state.factory_running_until = Some(completion);
        state.status = "running".to_string();
        self.schedule(completion, EventKind::Factory, pin_id);
        true
    }

    fn initialize(&mut self) {
        for pin_id in self.pin_order.clone() {
            let pin = self.states.get(&pin_id).unwrap().definition.clone();
            if pin.kind == PinKind::Extractor
                && pin
                    .extractor_cycle_time
                    .is_some_and(|cycle_time| cycle_time > 0)
            {
                let cycle_time = pin.extractor_cycle_time.unwrap();
                let mut next_completion =
                    pin.last_cycle_start.unwrap_or(self.checkpoint) + Duration::seconds(cycle_time);
                while next_completion <= self.checkpoint {
                    next_completion += Duration::seconds(cycle_time);
                }
                if pin
                    .expiry_time
                    .is_none_or(|expiry| next_completion <= expiry)
                {
                    self.states.get_mut(&pin_id).unwrap().status = "active".to_string();
                    self.schedule(next_completion, EventKind::Extractor, pin_id);
                } else {
                    self.states.get_mut(&pin_id).unwrap().status = "expired".to_string();
                }
            } else if pin.kind == PinKind::Factory && pin.schematic.is_some() {
                let schematic = pin.schematic.as_ref().unwrap();
                let completion = pin
                    .last_cycle_start
                    .map(|start| start + Duration::seconds(schematic.cycle_time));
                if completion.is_some_and(|completion| completion > self.checkpoint) {
                    let completion = completion.unwrap();
                    let state = self.states.get_mut(&pin_id).unwrap();
                    state.factory_running_until = Some(completion);
                    state.status = "running".to_string();
                    self.schedule(completion, EventKind::Factory, pin_id);
                } else {
                    self.try_start_factory(pin_id, self.checkpoint);
                }
            }
        }
    }

    fn run(&mut self, max_events: usize) -> (usize, bool) {
        let mut events_processed = 0;
        let mut truncated = false;
        while let Some(Reverse((when, _, kind, pin_id))) = self.events.pop() {
            if when > self.target {
                break;
            }
            if events_processed >= max_events {
                truncated = true;
                break;
            }
            events_processed += 1;
            if !self.states.contains_key(&pin_id) {
                continue;
            }
            match kind {
                EventKind::Extractor => self.process_extractor(pin_id, when),
                EventKind::Factory => self.process_factory(pin_id, when),
            }
        }
        (events_processed, truncated)
    }

    fn process_extractor(&mut self, pin_id: i64, when: DateTime<Utc>) {
        let pin = self.states.get(&pin_id).unwrap().definition.clone();
        if pin.expiry_time.is_some_and(|expiry| when > expiry) {
            self.states.get_mut(&pin_id).unwrap().status = "expired".to_string();
            return;
        }
        let cycle_time = pin.extractor_cycle_time.unwrap_or(0);
        let Some(product_type_id) = pin.extractor_product_type_id else {
            self.states.get_mut(&pin_id).unwrap().status = "idle".to_string();
            return;
        };
        let base_quantity = pin.extractor_quantity_per_cycle.unwrap_or(0);
        if cycle_time <= 0 || base_quantity <= 0 {
            self.states.get_mut(&pin_id).unwrap().status = "idle".to_string();
            return;
        }
        let quantity = if let Some(installed) = pin.install_time {
            let elapsed = when.signed_duration_since(installed).num_milliseconds() as f64 / 1000.0;
            let cycle_index = ((elapsed / cycle_time as f64).floor() as i64 - 1).max(0);
            extractor_cycle_output(
                cycle_index,
                cycle_time,
                base_quantity,
                pin.extractor_decay_factor,
                pin.extractor_noise_factor,
            )
        } else {
            base_quantity
        };
        *self
            .produced
            .entry(pin_id)
            .or_default()
            .entry(product_type_id)
            .or_default() += quantity;
        self.route_output(pin_id, product_type_id, quantity, when);
        let next_completion = when + Duration::seconds(cycle_time);
        if pin
            .expiry_time
            .is_none_or(|expiry| next_completion <= expiry)
        {
            self.schedule(next_completion, EventKind::Extractor, pin_id);
        } else {
            self.states.get_mut(&pin_id).unwrap().status = "expired".to_string();
        }
    }

    fn process_factory(&mut self, pin_id: i64, when: DateTime<Utc>) {
        let Some(schematic) = self
            .states
            .get(&pin_id)
            .and_then(|state| state.definition.schematic.clone())
        else {
            return;
        };
        self.states.get_mut(&pin_id).unwrap().factory_running_until = None;
        *self
            .produced
            .entry(pin_id)
            .or_default()
            .entry(schematic.output_type_id)
            .or_default() += schematic.output_quantity;
        let delivered = self.route_output(
            pin_id,
            schematic.output_type_id,
            schematic.output_quantity,
            when,
        );
        if delivered {
            self.try_start_factory(pin_id, when);
        } else {
            self.states.get_mut(&pin_id).unwrap().status = "blocked".to_string();
        }
    }

    fn finalize(&mut self) {
        for pin_id in self.pin_order.clone() {
            let state = self.states.get(&pin_id).unwrap();
            let status = if state.definition.kind == PinKind::Factory
                && self.blocked.contains_key(&pin_id)
            {
                Some("blocked")
            } else if state.definition.kind == PinKind::Factory
                && state.factory_running_until.is_some()
            {
                Some("running")
            } else if state.definition.kind == PinKind::Storage {
                if self
                    .capacity_remaining(pin_id)
                    .is_some_and(|remaining| remaining < 0.001)
                {
                    Some("full")
                } else {
                    Some("online")
                }
            } else if state.definition.kind == PinKind::Extractor
                && state
                    .definition
                    .expiry_time
                    .is_some_and(|expiry| expiry <= self.target)
            {
                Some("expired")
            } else {
                None
            };
            if let Some(status) = status {
                self.states.get_mut(&pin_id).unwrap().status = status.to_string();
            }
        }
    }
}

fn build_result(
    states: BTreeMap<i64, PinState>,
    checkpoint: Option<DateTime<Utc>>,
    target: DateTime<Utc>,
    events_processed: usize,
    is_projection: bool,
    truncated: bool,
    produced: BTreeMap<i64, BTreeMap<i64, i64>>,
    blocked: BTreeMap<i64, BTreeMap<i64, i64>>,
) -> ColonySimulationResult {
    ColonySimulationResult {
        checkpoint_at: checkpoint.map(iso),
        projected_at: iso(target),
        is_projection,
        events_processed,
        truncated,
        pins: states
            .into_iter()
            .map(|(pin_id, state)| {
                (
                    pin_id,
                    PinSimulationResult {
                        contents: state.contents,
                        status: state.status,
                        produced: produced.get(&pin_id).cloned().unwrap_or_default(),
                        blocked: blocked.get(&pin_id).cloned().unwrap_or_default(),
                    },
                )
            })
            .collect(),
    }
}
