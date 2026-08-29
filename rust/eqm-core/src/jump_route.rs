use std::cmp::Ordering;
use std::collections::{BinaryHeap, HashMap, HashSet};

use serde::{Deserialize, Serialize};

pub const INPUT_SCHEMA: &str = "eqm.jump-route-input.v1";
pub const OUTPUT_SCHEMA: &str = "eqm.jump-route-output.v1";

#[derive(Debug, Clone, Deserialize)]
pub struct JumpRouteInput {
    pub schema_version: String,
    pub origin_system_id: i64,
    pub destination_system_id: i64,
    pub max_range_ly: f64,
    pub destination_allowed: bool,
    #[serde(default)]
    pub avoid_system_ids: Vec<i64>,
    pub systems: Vec<JumpSystem>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct JumpSystem {
    pub system_id: i64,
    pub name: String,
    pub x_ly: f64,
    pub y_ly: f64,
    pub z_ly: f64,
    pub eligible_midpoint: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct JumpRouteOutput {
    pub schema_version: String,
    pub path_system_ids: Vec<i64>,
    pub total_distance_ly: f64,
}

#[derive(Debug, Clone, Copy)]
struct QueueState {
    priority: f64,
    cost: f64,
    system_id: i64,
}

impl PartialEq for QueueState {
    fn eq(&self, other: &Self) -> bool {
        self.priority == other.priority
            && self.cost == other.cost
            && self.system_id == other.system_id
    }
}

impl Eq for QueueState {}

impl PartialOrd for QueueState {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for QueueState {
    fn cmp(&self, other: &Self) -> Ordering {
        other
            .priority
            .partial_cmp(&self.priority)
            .unwrap_or(Ordering::Equal)
            .then_with(|| {
                other
                    .cost
                    .partial_cmp(&self.cost)
                    .unwrap_or(Ordering::Equal)
            })
            .then_with(|| other.system_id.cmp(&self.system_id))
    }
}

fn distance(left: &JumpSystem, right: &JumpSystem) -> f64 {
    ((left.x_ly - right.x_ly).powi(2)
        + (left.y_ly - right.y_ly).powi(2)
        + (left.z_ly - right.z_ly).powi(2))
    .sqrt()
}

fn grid_key(system: &JumpSystem, cell_size: f64) -> (i64, i64, i64) {
    (
        (system.x_ly / cell_size).floor() as i64,
        (system.y_ly / cell_size).floor() as i64,
        (system.z_ly / cell_size).floor() as i64,
    )
}

fn neighboring_ids(
    system: &JumpSystem,
    grid: &HashMap<(i64, i64, i64), Vec<i64>>,
    cell_size: f64,
) -> Vec<i64> {
    let (sx, sy, sz) = grid_key(system, cell_size);
    let mut candidates = Vec::new();
    for dx in -1..=1 {
        for dy in -1..=1 {
            for dz in -1..=1 {
                if let Some(ids) = grid.get(&(sx + dx, sy + dy, sz + dz)) {
                    candidates.extend(ids);
                }
            }
        }
    }
    candidates
}

pub fn evaluate_jump_route(input: JumpRouteInput) -> Result<JumpRouteOutput, String> {
    if input.schema_version != INPUT_SCHEMA {
        return Err(format!(
            "unsupported jump route schema: {}",
            input.schema_version
        ));
    }
    if !input.max_range_ly.is_finite() || input.max_range_ly <= 0.0 {
        return Err("max_range_ly must be a positive finite number".to_string());
    }
    if input.origin_system_id == input.destination_system_id {
        return Ok(JumpRouteOutput {
            schema_version: OUTPUT_SCHEMA.to_string(),
            path_system_ids: vec![input.origin_system_id],
            total_distance_ly: 0.0,
        });
    }

    let by_id: HashMap<i64, &JumpSystem> = input
        .systems
        .iter()
        .map(|system| (system.system_id, system))
        .collect();
    if !by_id.contains_key(&input.origin_system_id) {
        return Err("origin system is missing from the route graph".to_string());
    }
    let destination = by_id
        .get(&input.destination_system_id)
        .ok_or_else(|| "destination system is missing from the route graph".to_string())?;

    let mut grid: HashMap<(i64, i64, i64), Vec<i64>> = HashMap::new();
    for system in &input.systems {
        grid.entry(grid_key(system, input.max_range_ly))
            .or_default()
            .push(system.system_id);
    }

    let mut avoid: HashSet<i64> = input.avoid_system_ids.into_iter().collect();
    avoid.remove(&input.origin_system_id);
    avoid.remove(&input.destination_system_id);
    let mut distances: HashMap<i64, f64> = HashMap::from([(input.origin_system_id, 0.0)]);
    let mut parent: HashMap<i64, Option<i64>> = HashMap::from([(input.origin_system_id, None)]);
    let mut queue = BinaryHeap::from([QueueState {
        priority: 0.0,
        cost: 0.0,
        system_id: input.origin_system_id,
    }]);
    let mut visited = HashSet::new();

    while let Some(state) = queue.pop() {
        if !visited.insert(state.system_id) {
            continue;
        }
        if state.system_id == input.destination_system_id {
            break;
        }
        let current = by_id[&state.system_id];
        for candidate_id in neighboring_ids(current, &grid, input.max_range_ly) {
            if candidate_id == state.system_id
                || visited.contains(&candidate_id)
                || avoid.contains(&candidate_id)
            {
                continue;
            }
            let candidate = by_id[&candidate_id];
            if candidate_id == input.destination_system_id && !input.destination_allowed {
                continue;
            }
            if candidate_id != input.destination_system_id && !candidate.eligible_midpoint {
                continue;
            }
            let jump_distance = distance(current, candidate);
            if jump_distance > input.max_range_ly {
                continue;
            }
            let next_cost = state.cost + jump_distance;
            if next_cost < *distances.get(&candidate_id).unwrap_or(&f64::INFINITY) {
                distances.insert(candidate_id, next_cost);
                parent.insert(candidate_id, Some(state.system_id));
                queue.push(QueueState {
                    priority: next_cost + distance(candidate, destination) * 0.01,
                    cost: next_cost,
                    system_id: candidate_id,
                });
            }
        }
    }

    if !parent.contains_key(&input.destination_system_id) {
        return Err(format!(
            "No jump route found within {:.2} LY range. Try higher JDC or a different midpoint.",
            input.max_range_ly
        ));
    }
    let mut path = Vec::new();
    let mut cursor = Some(input.destination_system_id);
    while let Some(system_id) = cursor {
        path.push(system_id);
        cursor = parent[&system_id];
    }
    path.reverse();
    Ok(JumpRouteOutput {
        schema_version: OUTPUT_SCHEMA.to_string(),
        path_system_ids: path,
        total_distance_ly: distances[&input.destination_system_id],
    })
}
