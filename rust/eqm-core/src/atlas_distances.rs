//! Unweighted stargate distances for agent/store discovery, not safety routing.
use std::collections::{BTreeMap, HashMap, VecDeque};
use serde::{Deserialize, Serialize};

#[derive(Deserialize)]
pub struct Input { pub origin: u64, pub edges: Vec<[u64; 2]> }
#[derive(Serialize)]
pub struct Output { pub schema_version: &'static str, pub distances: BTreeMap<u64, u32> }

pub fn calculate(input: Input) -> Output {
    let mut graph: HashMap<u64, Vec<u64>> = HashMap::new();
    for [a,b] in input.edges { graph.entry(a).or_default().push(b); }
    let mut distances = BTreeMap::from([(input.origin, 0)]);
    let mut queue = VecDeque::from([input.origin]);
    while let Some(current) = queue.pop_front() {
        let next_distance = distances[&current] + 1;
        for &next in graph.get(&current).into_iter().flatten() {
            if let std::collections::btree_map::Entry::Vacant(entry) = distances.entry(next) {
                entry.insert(next_distance); queue.push_back(next);
            }
        }
    }
    Output { schema_version: "eqm.atlas-distances.v1", distances }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn cycles_duplicates_shortcuts_and_unreachable() {
        let result = calculate(Input { origin: 1, edges: vec![[1,2],[2,1],[2,3],[1,3],[3,4],[1,2],[9,8]] });
        assert_eq!(result.distances, BTreeMap::from([(1,0),(2,1),(3,1),(4,2)]));
    }
    #[test]
    fn isolated_origin_is_zero_jumps() {
        assert_eq!(calculate(Input { origin: 7, edges: vec![] }).distances, BTreeMap::from([(7,0)]));
    }
}
