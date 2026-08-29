use eqm_core::killboard_analytics::{evaluate_killboard_analytics, KillboardAnalyticsInput};

fn evaluate(json: &str) -> serde_json::Value {
    let input: KillboardAnalyticsInput = serde_json::from_str(json).unwrap();
    serde_json::to_value(evaluate_killboard_analytics(input).unwrap()).unwrap()
}

#[test]
fn combat_reduction_builds_exact_kpis_rankings_streaks_and_timeline() {
    let result = evaluate(r#"{
      "schema_version":"eqm.killboard-analytics-input.v1","as_of_date":"2026-08-29","events":[
        {"date":"2026-08-29","is_kill":true,"is_loss":false,"value_cents":10000,"solo":true,"damage_taken":100,
         "victim_hull":"Cyclone","system_name":"Amamake","region_name":"Heimatar","security_class":"Lowsec","kill_opponent":"Enemy One","loss_opponents":[],
         "matching_attackers":[{"ship_name":"Harpy","damage_done":60,"final_blow":true,"character_name":"Alice"},{"ship_name":"Keres","damage_done":40,"final_blow":false,"character_name":"Bob"}]},
        {"date":"2026-08-28","is_kill":true,"is_loss":true,"value_cents":5000,"solo":false,"damage_taken":50,
         "victim_hull":"Drake","system_name":"Amamake","region_name":"Heimatar","security_class":"Lowsec","kill_opponent":"Enemy Two","loss_opponents":["Enemy Three"],
         "matching_attackers":[{"ship_name":"Harpy","damage_done":20,"final_blow":false,"character_name":"Alice"}]},
        {"date":"2026-08-27","is_kill":false,"is_loss":true,"value_cents":null,"solo":null,"damage_taken":0,
         "victim_hull":"Harpy","system_name":"Tama","region_name":"The Citadel","security_class":"Lowsec","kill_opponent":null,"loss_opponents":["Enemy One"],"matching_attackers":[]}
      ]
    }"#);
    assert_eq!(result["summary"]["kills"], 2);
    assert_eq!(result["summary"]["losses"], 2);
    assert_eq!(result["summary"]["isk_destroyed_cents"], 15000);
    assert_eq!(result["summary"]["isk_lost_cents"], 5000);
    assert_eq!(result["summary"]["efficiency_rate_units"], 7_500_000_000_i64);
    assert_eq!(result["summary"]["damage_contribution_rate_units"], 8_000_000_000_i64);
    assert_eq!(result["unknown_value_records"], 1);
    assert_eq!(result["streaks"]["current_kind"], "kill");
    assert_eq!(result["streaks"]["current"], 2);
    assert_eq!(result["streaks"]["longest_kill"], 2);
    assert_eq!(result["streaks"]["longest_loss"], 2);
    assert_eq!(result["hulls"]["most_used"][0]["name"], "Harpy");
    assert_eq!(result["geography"]["systems"][0]["count"], 2);
    assert_eq!(result["opponents"][0]["name"], "Enemy One");
    assert_eq!(result["opponents"][0]["count"], 2);
    assert_eq!(result["wingmates"][0]["characters"], serde_json::json!(["Alice", "Bob"]));
    assert_eq!(result["timeline"][0]["date"], "2026-08-27");
}

#[test]
fn empty_contract_matches_the_python_zero_semantics() {
    let result = evaluate(r#"{"schema_version":"eqm.killboard-analytics-input.v1","as_of_date":"2026-08-29","events":[]}"#);
    assert_eq!(result["summary"]["kills"], 0);
    assert!(result["summary"]["efficiency_rate_units"].is_null());
    assert!(result["summary"]["inactivity_days"].is_null());
    assert_eq!(result["timeline"], serde_json::json!([]));
}

#[test]
fn equal_rank_counts_keep_first_encounter_order() {
    let result = evaluate(r#"{
      "schema_version":"eqm.killboard-analytics-input.v1","as_of_date":"2026-08-29","events":[
        {"date":"2026-08-29","is_kill":false,"is_loss":false,"value_cents":null,"solo":null,"damage_taken":0,"victim_hull":"A","system_name":"First","region_name":null,"security_class":"Unknown","kill_opponent":null,"loss_opponents":[],"matching_attackers":[]},
        {"date":"2026-08-28","is_kill":false,"is_loss":false,"value_cents":null,"solo":null,"damage_taken":0,"victim_hull":"B","system_name":"Second","region_name":null,"security_class":"Unknown","kill_opponent":null,"loss_opponents":[],"matching_attackers":[]}
      ]
    }"#);
    assert_eq!(result["geography"]["systems"][0]["name"], "First");
    assert_eq!(result["geography"]["systems"][1]["name"], "Second");
}
