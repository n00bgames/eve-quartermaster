use std::cmp::Ordering;
use std::collections::{HashMap, HashSet};

use chrono::{DateTime, Utc};
use serde::Deserialize;
use serde_json::{json, Value};

const SCHEMA: &str = "eqm.planetary-analytics.v1";
const TIERS: [(&str, &str); 5] = [
    ("P0", "Raw resources"),
    ("P1", "Basic commodities"),
    ("P2", "Refined commodities"),
    ("P3", "Specialized commodities"),
    ("P4", "Advanced commodities"),
];

#[derive(Debug, Deserialize)]
pub struct PlanetaryAnalyticsInput {
    pub schema_version: String,
    pub days: i64,
    pub cutoff: String,
    #[serde(default)]
    pub history: Vec<SnapshotRow>,
    #[serde(default)]
    pub current: Vec<SnapshotRow>,
    #[serde(default)]
    pub anonymous_character_ids: Vec<i64>,
}

#[derive(Debug, Deserialize)]
pub struct SnapshotRow {
    pub character_id: i64,
    pub character_name: String,
    pub product_type_id: i64,
    pub product_name: String,
    pub tier: String,
    pub unit_volume: f64,
    #[serde(default)]
    pub estimated_units_since_previous: f64,
    #[serde(default)]
    pub projected_units_per_day: f64,
    #[serde(default)]
    pub interval_started_at: Option<String>,
    pub captured_at: String,
}

#[derive(Debug, Clone)]
struct CharacterProduct {
    character_id: i64,
    character_name: String,
    product_type_id: i64,
    product_name: String,
    tier: String,
    estimated_units: f64,
    estimated_volume: f64,
    current_units_per_day: f64,
    current_volume_per_day: f64,
    order: usize,
}

fn parse_utc(value: &str, label: &str) -> Result<DateTime<Utc>, String> {
    DateTime::parse_from_rfc3339(value)
        .map(|stamp| stamp.with_timezone(&Utc))
        .map_err(|error| format!("invalid {label}: {error}"))
}

fn windowed_estimate(row: &SnapshotRow, cutoff: DateTime<Utc>) -> Result<f64, String> {
    let captured = parse_utc(&row.captured_at, "captured_at")?;
    let Some(started_at) = row.interval_started_at.as_deref() else {
        return Ok(row.estimated_units_since_previous);
    };
    let started = parse_utc(started_at, "interval_started_at")?;
    if started >= cutoff || captured <= cutoff {
        return Ok(row.estimated_units_since_previous);
    }
    let total = (captured - started).num_milliseconds() as f64 / 1_000.0;
    let visible = (captured - cutoff).num_milliseconds() as f64 / 1_000.0;
    if total > 0.0 {
        Ok(row.estimated_units_since_previous * (visible / total).clamp(0.0, 1.0))
    } else {
        Ok(row.estimated_units_since_previous)
    }
}

fn descending_pair(left: &CharacterProduct, right: &CharacterProduct) -> Ordering {
    right
        .estimated_volume
        .total_cmp(&left.estimated_volume)
        .then_with(|| {
            right
                .current_volume_per_day
                .total_cmp(&left.current_volume_per_day)
        })
        .then_with(|| left.order.cmp(&right.order))
}

fn character_product_json(row: &CharacterProduct) -> Value {
    json!({
        "character_id": row.character_id,
        "character_name": row.character_name,
        "product_type_id": row.product_type_id,
        "product_name": row.product_name,
        "tier": row.tier,
        "estimated_units": row.estimated_units,
        "estimated_volume": row.estimated_volume,
        "current_units_per_day": row.current_units_per_day,
        "current_volume_per_day": row.current_volume_per_day,
    })
}

fn ensure_character_product(
    rows: &mut Vec<CharacterProduct>,
    indexes: &mut HashMap<(i64, i64), usize>,
    source: &SnapshotRow,
) -> usize {
    let key = (source.character_id, source.product_type_id);
    if let Some(index) = indexes.get(&key) {
        return *index;
    }
    let index = rows.len();
    indexes.insert(key, index);
    rows.push(CharacterProduct {
        character_id: source.character_id,
        character_name: source.character_name.clone(),
        product_type_id: source.product_type_id,
        product_name: source.product_name.clone(),
        tier: source.tier.clone(),
        estimated_units: 0.0,
        estimated_volume: 0.0,
        current_units_per_day: 0.0,
        current_volume_per_day: 0.0,
        order: index,
    });
    index
}

pub fn evaluate_planetary_analytics(input: PlanetaryAnalyticsInput) -> Result<Value, String> {
    if input.schema_version != SCHEMA {
        return Err(format!(
            "unsupported planetary analytics schema: {}",
            input.schema_version
        ));
    }
    let cutoff = parse_utc(&input.cutoff, "cutoff")?;
    let anonymous: HashSet<i64> = input.anonymous_character_ids.into_iter().collect();
    let mut rows: Vec<CharacterProduct> = Vec::new();
    let mut indexes: HashMap<(i64, i64), usize> = HashMap::new();

    for source in &input.history {
        let units = windowed_estimate(source, cutoff)?;
        let index = ensure_character_product(&mut rows, &mut indexes, source);
        rows[index].estimated_units += units;
        rows[index].estimated_volume += units * source.unit_volume;
    }
    for source in &input.current {
        let index = ensure_character_product(&mut rows, &mut indexes, source);
        rows[index].current_units_per_day += source.projected_units_per_day;
        rows[index].current_volume_per_day += source.projected_units_per_day * source.unit_volume;
    }
    rows.sort_by(descending_pair);

    #[derive(Clone)]
    struct Product {
        product_type_id: i64,
        product_name: String,
        tier: String,
        estimated_units: f64,
        estimated_volume: f64,
        current_units_per_day: f64,
        current_volume_per_day: f64,
        top_character: Option<String>,
        top_score: f64,
        order: usize,
    }
    struct TierTotals {
        estimated_units: f64,
        estimated_volume: f64,
        current_units_per_day: f64,
        current_volume_per_day: f64,
        products: HashSet<i64>,
        characters: HashSet<i64>,
    }
    let mut products: Vec<Product> = Vec::new();
    let mut product_indexes: HashMap<i64, usize> = HashMap::new();
    let mut tier_totals: HashMap<String, TierTotals> = TIERS
        .iter()
        .map(|(tier, _)| {
            (
                (*tier).to_string(),
                TierTotals {
                    estimated_units: 0.0,
                    estimated_volume: 0.0,
                    current_units_per_day: 0.0,
                    current_volume_per_day: 0.0,
                    products: HashSet::new(),
                    characters: HashSet::new(),
                },
            )
        })
        .collect();

    for row in &rows {
        let product_index = *product_indexes
            .entry(row.product_type_id)
            .or_insert_with(|| {
                let index = products.len();
                products.push(Product {
                    product_type_id: row.product_type_id,
                    product_name: row.product_name.clone(),
                    tier: row.tier.clone(),
                    estimated_units: 0.0,
                    estimated_volume: 0.0,
                    current_units_per_day: 0.0,
                    current_volume_per_day: 0.0,
                    top_character: None,
                    top_score: -1.0,
                    order: index,
                });
                index
            });
        let product = &mut products[product_index];
        product.estimated_units += row.estimated_units;
        product.estimated_volume += row.estimated_volume;
        product.current_units_per_day += row.current_units_per_day;
        product.current_volume_per_day += row.current_volume_per_day;
        let score = if row.estimated_units != 0.0 {
            row.estimated_units
        } else {
            row.current_units_per_day
        };
        if !anonymous.contains(&row.character_id) && score > product.top_score {
            product.top_score = score;
            product.top_character = Some(row.character_name.clone());
        }
        let tier = tier_totals
            .get_mut(&row.tier)
            .ok_or_else(|| format!("unsupported commodity tier: {}", row.tier))?;
        tier.estimated_units += row.estimated_units;
        tier.estimated_volume += row.estimated_volume;
        tier.current_units_per_day += row.current_units_per_day;
        tier.current_volume_per_day += row.current_volume_per_day;
        tier.products.insert(row.product_type_id);
        tier.characters.insert(row.character_id);
    }
    products.sort_by(|left, right| {
        right
            .estimated_volume
            .total_cmp(&left.estimated_volume)
            .then_with(|| {
                right
                    .current_volume_per_day
                    .total_cmp(&left.current_volume_per_day)
            })
            .then_with(|| left.order.cmp(&right.order))
    });
    let product_rows: Vec<Value> = products
        .into_iter()
        .map(|row| {
            json!({
                "product_type_id": row.product_type_id,
                "product_name": row.product_name,
                "tier": row.tier,
                "estimated_units": row.estimated_units,
                "estimated_volume": row.estimated_volume,
                "current_units_per_day": row.current_units_per_day,
                "current_volume_per_day": row.current_volume_per_day,
                "top_character": row.top_character,
            })
        })
        .collect();
    let tier_rows: Vec<Value> = TIERS
        .iter()
        .map(|(tier, label)| {
            let totals = tier_totals.get(*tier).expect("tier initialized");
            json!({
                "tier": tier,
                "label": label,
                "estimated_units": totals.estimated_units,
                "estimated_volume": totals.estimated_volume,
                "current_units_per_day": totals.current_units_per_day,
                "current_volume_per_day": totals.current_volume_per_day,
                "product_count": totals.products.len(),
                "character_count": totals.characters.len(),
            })
        })
        .collect();
    let character_ids: HashSet<i64> = rows.iter().map(|row| row.character_id).collect();
    Ok(json!({
        "schema_version": SCHEMA,
        "days": input.days,
        "has_history": rows.iter().any(|row| row.estimated_units > 0.0),
        "cards": {
            "estimated_volume": rows.iter().map(|row| row.estimated_volume).sum::<f64>(),
            "current_volume_per_day": rows.iter().map(|row| row.current_volume_per_day).sum::<f64>(),
            "product_count": product_rows.len(),
            "character_count": character_ids.len(),
        },
        "tiers": tier_rows,
        "products": product_rows,
        "character_products": rows.iter().filter(|row| !anonymous.contains(&row.character_id)).map(character_product_json).collect::<Vec<_>>(),
    }))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn row(character_id: i64, product_type_id: i64, units: f64, rate: f64) -> SnapshotRow {
        SnapshotRow {
            character_id,
            character_name: format!("Pilot {character_id}"),
            product_type_id,
            product_name: format!("Product {product_type_id}"),
            tier: "P2".to_string(),
            unit_volume: 1.5,
            estimated_units_since_previous: units,
            projected_units_per_day: rate,
            interval_started_at: Some("2026-08-01T00:00:00+00:00".to_string()),
            captured_at: "2026-08-03T00:00:00+00:00".to_string(),
        }
    }

    #[test]
    fn aggregates_history_current_rates_and_anonymity() {
        let output = evaluate_planetary_analytics(PlanetaryAnalyticsInput {
            schema_version: SCHEMA.to_string(),
            days: 1,
            cutoff: "2026-08-02T00:00:00+00:00".to_string(),
            history: vec![row(1, 44, 100.0, 0.0), row(2, 44, 50.0, 0.0)],
            current: vec![row(1, 44, 0.0, 40.0), row(2, 44, 0.0, 20.0)],
            anonymous_character_ids: vec![1],
        })
        .unwrap();
        assert_eq!(output["cards"]["estimated_volume"], 112.5);
        assert_eq!(output["cards"]["current_volume_per_day"], 90.0);
        assert_eq!(output["products"][0]["top_character"], "Pilot 2");
        assert_eq!(output["character_products"].as_array().unwrap().len(), 1);
        assert_eq!(output["tiers"][2]["product_count"], 1);
    }
}
