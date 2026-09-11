use serde::Deserialize;
use serde_json::{json, Value};
use std::collections::BTreeMap;

#[derive(Deserialize)]
pub struct Ingredient {
    pub type_id: u64,
    pub quantity: u64,
}
#[derive(Deserialize)]
pub struct ProductionInput {
    pub cycle_time: u64,
    pub output_quantity: u64,
    pub factories: u64,
    pub inputs: Vec<Ingredient>,
    pub inventory: BTreeMap<u64, u64>,
}

pub fn calculate(p: ProductionInput) -> Result<Value, String> {
    if p.inputs.is_empty()
        || p.inputs.len() > 32
        || p.factories == 0
        || p.factories > 10000
        || p.cycle_time == 0
        || p.cycle_time > 86400
        || p.output_quantity == 0
        || p.output_quantity > 1000000
        || p.inputs
            .iter()
            .any(|i| i.quantity == 0 || i.quantity > 1000000000)
        || p.inventory.values().any(|q| *q > 1000000000000)
    {
        return Err("Invalid production inputs".into());
    }
    let mut requirements = BTreeMap::<u64, u64>::new();
    for i in p.inputs {
        *requirements.entry(i.type_id).or_default() += i.quantity;
    }
    let batches = requirements
        .iter()
        .map(|(id, q)| p.inventory.get(id).unwrap_or(&0) / q)
        .min()
        .unwrap_or(0);
    let full_rounds = batches / p.factories;
    let final_factories = batches % p.factories;
    let seconds = (full_rounds + u64::from(final_factories > 0)) * p.cycle_time;
    let ingredients: Vec<Value> = requirements
        .iter()
        .map(|(id, q)| {
            let available = *p.inventory.get(id).unwrap_or(&0);
            json!({"type_id": id, "available": available, "consumed": batches*q,
            "remaining": available-batches*q, "limiting": available/q == batches,
            "required_per_round": q*p.factories})
        })
        .collect();
    Ok(
        json!({"schema_version":"eqm.pi-production.v1", "total_batches":batches,
        "output_quantity": batches*p.output_quantity, "duration_seconds":seconds,
        "full_capacity_seconds":full_rounds*p.cycle_time, "final_round_factories":final_factories,
        "ingredients":ingredients}),
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn unequal_stock_and_partial_final_round() {
        let p=serde_json::from_value(json!({"cycle_time":3600,"output_quantity":5,"factories":3,
            "inputs":[{"type_id":1,"quantity":40},{"type_id":2,"quantity":40}],"inventory":{"1":200,"2":300}})).unwrap();
        let r = calculate(p).unwrap();
        assert_eq!(r["total_batches"], 5);
        assert_eq!(r["output_quantity"], 25);
        assert_eq!(r["duration_seconds"], 7200);
        assert_eq!(r["full_capacity_seconds"], 3600);
        assert_eq!(r["final_round_factories"], 2);
        assert_eq!(r["ingredients"][1]["remaining"], 100);
    }
    #[test]
    fn missing_ingredient_produces_nothing() {
        let p = serde_json::from_value(json!({"cycle_time":3600,"output_quantity":5,"factories":1,
            "inputs":[{"type_id":1,"quantity":40}],"inventory":{}}))
        .unwrap();
        assert_eq!(calculate(p).unwrap()["duration_seconds"], 0);
    }
}
