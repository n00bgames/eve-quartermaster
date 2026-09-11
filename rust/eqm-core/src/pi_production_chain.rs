//! Complete-cycle expansion with shared feedstock across a PI recipe DAG.
use serde::Deserialize;
use serde_json::{json, Value};
use std::cmp::Reverse;
use std::collections::{BTreeMap, BTreeSet, BinaryHeap};

#[derive(Clone, Deserialize)]
pub struct Input {
    pub type_id: u64,
    pub quantity: u64,
}
#[derive(Clone, Deserialize)]
pub struct Recipe {
    pub id: u64,
    pub output_type_id: u64,
    pub output_quantity: u64,
    pub cycle_time: u64,
    pub inputs: Vec<Input>,
}
#[derive(Deserialize)]
pub struct Request {
    pub target_id: u64,
    pub feed_tier: u8,
    pub recipes: Vec<Recipe>,
    pub inventory: BTreeMap<u64, u64>,
    pub factories: BTreeMap<u64, u64>,
}
fn tier(
    id: u64,
    recipes: &BTreeMap<u64, Recipe>,
    tiers: &mut BTreeMap<u64, u8>,
    active: &mut BTreeSet<u64>,
) -> Result<u8, String> {
    if let Some(t) = tiers.get(&id) {
        return Ok(*t);
    }
    if !active.insert(id) || active.len() > 8 {
        return Err("Invalid or cyclic recipe catalog".into());
    }
    let mut t = 0;
    if let Some(r) = recipes.get(&id) {
        for i in &r.inputs {
            t = t.max(tier(i.type_id, recipes, tiers, active)? + 1);
        }
    }
    active.remove(&id);
    tiers.insert(id, t);
    Ok(t)
}
fn visit(
    id: u64,
    feed: u8,
    recipes: &BTreeMap<u64, Recipe>,
    tiers: &BTreeMap<u64, u8>,
    nodes: &mut BTreeSet<u64>,
) {
    if !nodes.insert(id) || tiers[&id] <= feed {
        return;
    }
    if let Some(r) = recipes.get(&id) {
        for i in &r.inputs {
            visit(i.type_id, feed, recipes, tiers, nodes);
        }
    }
}
#[derive(Default)]
struct Plan {
    demand: BTreeMap<u64, u64>,
    batches: BTreeMap<u64, u64>,
}
fn expand(
    n: u64,
    root: u64,
    order: &[u64],
    recipes: &BTreeMap<u64, Recipe>,
    feed: u8,
    tiers: &BTreeMap<u64, u8>,
) -> Result<Plan, String> {
    let mut p = Plan::default();
    p.demand.insert(
        root,
        n.checked_mul(recipes[&root].output_quantity)
            .ok_or("Quantity overflow")?,
    );
    for id in order {
        if tiers[id] <= feed {
            continue;
        }
        let r = &recipes[id];
        let demand = p.demand[id];
        let count = demand.div_ceil(r.output_quantity);
        p.batches.insert(*id, count);
        for input in &r.inputs {
            let q = count
                .checked_mul(input.quantity)
                .ok_or("Quantity overflow")?;
            let entry = p.demand.entry(input.type_id).or_default();
            *entry = entry.checked_add(q).ok_or("Quantity overflow")?;
        }
    }
    Ok(p)
}
struct Pipeline {
    duration: u64,
    first_start: BTreeMap<u64, u64>,
    finished: BTreeMap<u64, u64>,
}

// Run complete factory cycles concurrently. Deliver every completion at a timestamp
// before starting more work, so ready downstream jobs do not gain an artificial delay.
fn pipeline(
    root: u64,
    order: &[u64],
    recipes: &BTreeMap<u64, Recipe>,
    plan: &Plan,
    inventory: BTreeMap<u64, u64>,
    factories: &BTreeMap<u64, u64>,
) -> Result<Option<Pipeline>, String> {
    let mut stock = inventory;
    let mut remaining = plan.batches.clone();
    let mut active = BTreeMap::<u64, u64>::new();
    let mut events = BinaryHeap::<Reverse<(u64, u64, u64)>>::new();
    let mut result = Pipeline {
        duration: 0,
        first_start: BTreeMap::new(),
        finished: BTreeMap::new(),
    };
    let mut now = 0;
    let mut completed_events = 0;
    loop {
        for id in order
            .iter()
            .rev()
            .filter(|id| plan.batches.contains_key(id))
        {
            let r = &recipes[id];
            let running = *active.get(id).unwrap_or(&0);
            let mut count = remaining[id].min(*factories.get(&r.id).unwrap_or(&1) - running);
            let mut requirements = BTreeMap::<u64, u64>::new();
            for input in &r.inputs {
                *requirements.entry(input.type_id).or_default() += input.quantity;
            }
            for (type_id, quantity) in &requirements {
                count = count.min(*stock.get(type_id).unwrap_or(&0) / quantity);
            }
            if count == 0 {
                continue;
            }
            for (type_id, quantity) in requirements {
                *stock.entry(type_id).or_default() -= count * quantity;
            }
            *remaining.get_mut(id).unwrap() -= count;
            *active.entry(*id).or_default() += count;
            result.first_start.entry(*id).or_insert(now);
            events.push(Reverse((
                now.checked_add(r.cycle_time).ok_or("Duration overflow")?,
                *id,
                count,
            )));
        }
        let Some(Reverse((next_time, _, _))) = events.peek() else {
            if remaining.values().any(|n| *n > 0) {
                return Err("Production schedule could not complete".into());
            }
            return Ok(Some(result));
        };
        now = *next_time;
        while events
            .peek()
            .is_some_and(|Reverse((time, _, _))| *time == now)
        {
            let Reverse((_, id, count)) = events.pop().unwrap();
            completed_events += 1;
            // Keep very large stockpiles responsive; retain exact yield and staged
            // runtimes when a bounded event simulation cannot provide an ETA.
            if completed_events > 20_000 {
                return Ok(None);
            }
            *active.get_mut(&id).unwrap() -= count;
            let produced = count
                .checked_mul(recipes[&id].output_quantity)
                .ok_or("Quantity overflow")?;
            let entry = stock.entry(id).or_default();
            *entry = entry.checked_add(produced).ok_or("Quantity overflow")?;
            result.finished.insert(id, now);
            if id == root {
                result.duration = now;
            }
        }
    }
}

pub fn calculate(req: Request) -> Result<Value, String> {
    if req.recipes.is_empty()
        || req.recipes.len() > 512
        || req.feed_tier > 3
        || req.inventory.len() > 128
        || req.inventory.values().any(|q| *q > 1_000_000_000_000)
        || req.factories.len() > 128
        || req.factories.values().any(|q| *q == 0 || *q > 10000)
    {
        return Err("Invalid chain inputs".into());
    }
    let mut recipes = BTreeMap::new();
    let mut ids = BTreeSet::new();
    let mut root = None;
    for r in req.recipes {
        if r.output_quantity == 0
            || r.output_quantity > 1_000_000
            || r.cycle_time == 0
            || r.cycle_time > 86400
            || r.inputs.is_empty()
            || r.inputs.len() > 32
            || r.inputs
                .iter()
                .any(|i| i.quantity == 0 || i.quantity > 1_000_000_000)
            || !ids.insert(r.id)
            || recipes.contains_key(&r.output_type_id)
        {
            return Err("Invalid recipe catalog".into());
        }
        if r.id == req.target_id {
            root = Some(r.output_type_id);
        }
        recipes.insert(r.output_type_id, r);
    }
    let root = root.ok_or("Target recipe not found")?;
    let mut tiers = BTreeMap::new();
    let root_tier = tier(root, &recipes, &mut tiers, &mut BTreeSet::new())?;
    if req.feed_tier >= root_tier || root_tier > 4 {
        return Err("Feed tier must be below the selected product tier".into());
    }
    let mut nodes = BTreeSet::new();
    visit(root, req.feed_tier, &recipes, &tiers, &mut nodes);
    let mut order: Vec<u64> = nodes.into_iter().collect();
    order.sort_by_key(|id| (std::cmp::Reverse(tiers[id]), *id));
    let feeds: Vec<u64> = order
        .iter()
        .copied()
        .filter(|id| tiers[id] <= req.feed_tier)
        .collect();
    let feasible = |p: &Plan| {
        feeds
            .iter()
            .all(|id| p.demand[id] <= *req.inventory.get(id).unwrap_or(&0))
    };
    // Doubling + binary search keeps work bounded even for trillion-unit stockpiles.
    let mut low = 0;
    let mut high = 1u64;
    loop {
        match expand(high, root, &order, &recipes, req.feed_tier, &tiers) {
            Ok(p) if feasible(&p) => low = high,
            _ => break,
        }
        high = high.checked_mul(2).ok_or("Quantity overflow")?;
    }
    while low + 1 < high {
        let mid = low + (high - low) / 2;
        match expand(mid, root, &order, &recipes, req.feed_tier, &tiers) {
            Ok(p) if feasible(&p) => low = mid,
            _ => high = mid,
        }
    }
    let plan = expand(low, root, &order, &recipes, req.feed_tier, &tiers)?;
    let next = expand(low + 1, root, &order, &recipes, req.feed_tier, &tiers)?;
    let ingredients:Vec<Value>=feeds.iter().map(|id| {
        let available=*req.inventory.get(id).unwrap_or(&0); let used=plan.demand[id];
        json!({"type_id":id,"available":available,"consumed":used,"remaining":available-used,
            "limiting":next.demand[id]>available,"needed_for_next_batch":next.demand[id].saturating_sub(available)})
    }).collect();
    let schedule = pipeline(
        root,
        &order,
        &recipes,
        &plan,
        feeds
            .iter()
            .map(|id| (*id, *req.inventory.get(id).unwrap_or(&0)))
            .collect(),
        &req.factories,
    )?;
    let mut stages = Vec::new();
    let mut tier_seconds = BTreeMap::<u8, u64>::new();
    for id in order.iter().rev().filter(|id| tiers[id] > req.feed_tier) {
        let r = &recipes[id];
        let batches = plan.batches[id];
        let factories = *req.factories.get(&r.id).unwrap_or(&1);
        let duration = batches
            .div_ceil(factories)
            .checked_mul(r.cycle_time)
            .ok_or("Duration overflow")?;
        let entry = tier_seconds.entry(tiers[id]).or_default();
        *entry = (*entry).max(duration);
        let made = batches
            .checked_mul(r.output_quantity)
            .ok_or("Quantity overflow")?;
        stages.push(json!({"recipe_id":r.id,"type_id":id,"tier":tiers[id],"batches":batches,"produced":made,
            "consumed":if *id==root {0} else {plan.demand[id]},"remaining":if *id==root {0} else {made-plan.demand[id]},
            "factories":factories,"duration_seconds":duration,"final_round_factories":batches%factories,
            "first_start_seconds":schedule.as_ref().and_then(|s|s.first_start.get(id)),
            "finished_at_seconds":schedule.as_ref().and_then(|s|s.finished.get(id))}));
    }
    let duration = tier_seconds
        .values()
        .try_fold(0u64, |a, b| a.checked_add(*b))
        .ok_or("Duration overflow")?;
    let tier_summary: Vec<Value> = tier_seconds.iter().map(|(tier, runtime)| {
        let ids: Vec<_> = plan.batches.keys().filter(|id| tiers[id] == *tier).collect();
        json!({"tier":tier,"product_count":ids.len(),"runtime_seconds":runtime,
            "first_start_seconds":schedule.as_ref().and_then(|s|ids.iter().filter_map(|id|s.first_start.get(id)).min()),
            "finished_at_seconds":schedule.as_ref().and_then(|s|ids.iter().filter_map(|id|s.finished.get(id)).max())})
    }).collect();
    Ok(
        json!({"schema_version":"eqm.pi-production.v1","mode":"chain","feed_tier":req.feed_tier,
        "total_batches":low,"output_quantity":plan.demand[&root],"duration_seconds":duration,
        "ingredients":ingredients,"stages":stages,"tiers":tier_summary,
        "pipeline_duration_seconds":schedule.as_ref().map(|s|s.duration),
        "timing_method":if schedule.is_some() {"overlapping_cycles"} else {"staged_only_event_limit"}}),
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    fn catalog() -> Value {
        json!([
            {"id":1,"output_type_id":10,"output_quantity":20,"cycle_time":1800,"inputs":[{"type_id":1,"quantity":3000}]},
            {"id":2,"output_type_id":20,"output_quantity":5,"cycle_time":3600,"inputs":[{"type_id":10,"quantity":40}]},
            {"id":3,"output_type_id":30,"output_quantity":3,"cycle_time":3600,"inputs":[{"type_id":20,"quantity":10}]},
            {"id":4,"output_type_id":31,"output_quantity":3,"cycle_time":3600,"inputs":[{"type_id":20,"quantity":10}]},
            {"id":5,"output_type_id":40,"output_quantity":1,"cycle_time":3600,"inputs":[{"type_id":30,"quantity":4},{"type_id":31,"quantity":4},{"type_id":10,"quantity":2}]}
        ])
    }
    fn run(stock: Value) -> Value {
        calculate(serde_json::from_value(json!({"target_id":5,"feed_tier":2,"recipes":catalog(),"inventory":stock,"factories":{"3":2,"4":2}})).unwrap()).unwrap()
    }
    #[test]
    fn shared_p2_and_direct_p1_are_consumed_once() {
        let r = run(json!({"20":65,"10":10}));
        assert_eq!(r["output_quantity"], 2); // 3 cycles on each P3 line = 60 shared P2.
        assert_eq!(r["ingredients"][1]["remaining"], 6);
        assert_eq!(r["ingredients"][0]["remaining"], 5);
        assert_eq!(r["stages"][0]["produced"], 9);
        assert_eq!(r["stages"][0]["remaining"], 1);
        assert_eq!(r["duration_seconds"], 14400); // Sequential comparison.
        assert_eq!(r["pipeline_duration_seconds"], 10800); // P4 starts at hour 1.
        assert_eq!(r["tiers"][0]["runtime_seconds"], 7200);
        assert_eq!(r["tiers"][0]["product_count"], 2);
        assert_eq!(r["tiers"][1]["first_start_seconds"], 3600);
        assert_eq!(r["ingredients"][0]["limiting"], true);
    }
    #[test]
    fn zero_stock_and_complete_batch_rounding() {
        assert_eq!(run(json!({"20":39,"10":10}))["output_quantity"], 0);
        assert_eq!(run(json!({"20":40,"10":2}))["output_quantity"], 1);
        assert_eq!(run(json!({"20":100}))["output_quantity"], 0);
    }
    #[test]
    fn rejects_cycle_and_invalid_tier() {
        let mut c = catalog();
        c[0]["inputs"][0]["type_id"] = json!(40);
        assert!(calculate(
            serde_json::from_value(
                json!({"target_id":5,"feed_tier":2,"recipes":c,"inventory":{},"factories":{}})
            )
            .unwrap()
        )
        .is_err());
        assert!(calculate(serde_json::from_value(json!({"target_id":5,"feed_tier":4,"recipes":catalog(),"inventory":{},"factories":{}})).unwrap()).is_err());
    }
    #[test]
    fn large_stock_is_bounded_and_conserved() {
        let r = run(json!({"20":1_000_000_000_000u64,"10":1_000_000_000_000u64}));
        assert!(r["output_quantity"].as_u64().unwrap() > 1_000_000);
        assert_eq!(r["pipeline_duration_seconds"], Value::Null);
        assert_eq!(r["timing_method"], "staged_only_event_limit");
        for i in r["ingredients"].as_array().unwrap() {
            assert_eq!(
                i["consumed"].as_u64().unwrap() + i["remaining"].as_u64().unwrap(),
                1_000_000_000_000
            );
        }
    }
}

#[cfg(test)]
mod pipeline_examples {
    use super::*;
    #[test]
    fn screenshot_balanced_three_p3_lines_feed_two_p4_factories() {
        // Reproduce the screenshot's batch quantities and factory counts.
        let mut recipes = vec![
            json!({"id":1,"output_type_id":10,"output_quantity":20,"cycle_time":1800,"inputs":[{"type_id":1,"quantity":3000}]}),
        ];
        for id in 20..26 {
            recipes.push(json!({"id":id,"output_type_id":id,"output_quantity":5,"cycle_time":3600,"inputs":[{"type_id":10,"quantity":40}]}));
        }
        for (id, a, b) in [(30, 20, 21), (31, 22, 23), (32, 24, 25)] {
            recipes.push(json!({"id":id,"output_type_id":id,"output_quantity":3,"cycle_time":3600,"inputs":[{"type_id":a,"quantity":10},{"type_id":b,"quantity":10}]}));
        }
        recipes.push(json!({"id":40,"output_type_id":40,"output_quantity":1,"cycle_time":3600,"inputs":[{"type_id":30,"quantity":6},{"type_id":31,"quantity":6},{"type_id":32,"quantity":6}]}));
        let req = json!({"target_id":40,"feed_tier":2,"recipes":recipes,
            "inventory":{"20":4240,"21":11595,"22":6700,"23":10980,"24":8350,"25":6675},
            "factories":{"30":4,"31":4,"32":4,"40":2}});
        let result = calculate(serde_json::from_value(req.clone()).unwrap()).unwrap();
        assert_eq!(result["output_quantity"], 212);
        assert_eq!(result["pipeline_duration_seconds"], 107 * 3600); // 4d 11h, including first P3 cycle.
        assert_eq!(result["duration_seconds"], 212 * 3600);
        assert_eq!(result["tiers"][0]["runtime_seconds"], 106 * 3600);
        assert_eq!(result["tiers"][0]["product_count"], 3);
        assert_eq!(result["tiers"][1]["runtime_seconds"], 106 * 3600);
        let mut slow = req.clone();
        slow["factories"]["30"] = json!(2);
        let slow = calculate(serde_json::from_value(slow).unwrap()).unwrap();
        assert_eq!(slow["pipeline_duration_seconds"], 213 * 3600); // Slower one P3 line limits all P4.
        assert_eq!(slow["output_quantity"], 212);
        let mut empty = req;
        empty["inventory"] = json!({});
        assert_eq!(
            calculate(serde_json::from_value(empty).unwrap()).unwrap()["pipeline_duration_seconds"],
            0
        );
    }
}
