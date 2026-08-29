use eqm_core::battle_reports::{evaluate_battle_report, BattleReportInput};

fn payload(extra: &str) -> BattleReportInput {
    let value = format!(
        r#"{{
      "schema_version":"eqm.battle-report-input.v1","selected_character_id":1,"seed_killmail_id":2,"gap_minutes":15,{extra}
      "organization_overrides":[],"rows":[
        {{"killmail_id":1,"killmail_time":"2026-08-29T10:00:00+00:00","system":{{"system_id":3001,"system_name":"Arena","security_status":0.1,"region_name":"Test Region"}},
         "character_id":3,"character_name":"Opponent","corporation_id":20,"corporation_name":"Hostile","alliance_id":null,"alliance_name":null,"faction_id":null,
         "victim_name":"Opponent","timeline_victim_corporation_name":"Hostile","timeline_victim_alliance_name":null,"victim_ship":{{"type_id":200,"type_name":"Drake","ship_group_id":419,"ship_group_name":"Combat Battlecruiser"}},"damage_taken":1000,"estimated_total_value":200000000.0,"zkill_url":"https://zkillboard.com/kill/1/",
         "attackers":[
           {{"character_id":1,"character_name":"Selected","corporation_id":10,"corporation_name":"Friendly","alliance_id":null,"alliance_name":null,"faction_id":null,"ship":{{"type_id":100,"type_name":"Rifter","ship_group_id":25,"ship_group_name":"Frigate"}},"damage_done":700,"final_blow":true}},
           {{"character_id":2,"character_name":"Wingmate","corporation_id":10,"corporation_name":"Friendly","alliance_id":null,"alliance_name":null,"faction_id":null,"ship":{{"type_id":100,"type_name":"Rifter","ship_group_id":25,"ship_group_name":"Frigate"}},"damage_done":300,"final_blow":false}}
         ]}},
        {{"killmail_id":99,"killmail_time":"2026-08-29T10:05:00+00:00","system":{{"system_id":3001,"system_name":"Arena","security_status":0.1,"region_name":"Test Region"}},
         "character_id":99,"character_name":"Unrelated","corporation_id":99,"corporation_name":"Other","alliance_id":null,"alliance_name":null,"faction_id":null,
         "victim_name":"Unrelated","timeline_victim_corporation_name":"Other","timeline_victim_alliance_name":null,"victim_ship":null,"damage_taken":10,"estimated_total_value":999.0,"zkill_url":"https://zkillboard.com/kill/99/",
         "attackers":[{{"character_id":98,"character_name":"Other","corporation_id":98,"corporation_name":"Other","alliance_id":null,"alliance_name":null,"faction_id":null,"ship":null,"damage_done":10,"final_blow":true}}]}},
        {{"killmail_id":2,"killmail_time":"2026-08-29T10:10:00+00:00","system":{{"system_id":3001,"system_name":"Arena","security_status":0.1,"region_name":"Test Region"}},
         "character_id":2,"character_name":"Wingmate","corporation_id":10,"corporation_name":"Friendly","alliance_id":null,"alliance_name":null,"faction_id":null,
         "victim_name":"Wingmate","timeline_victim_corporation_name":"Friendly","timeline_victim_alliance_name":null,"victim_ship":{{"type_id":100,"type_name":"Rifter","ship_group_id":25,"ship_group_name":"Frigate"}},"damage_taken":500,"estimated_total_value":50000000.0,"zkill_url":"https://zkillboard.com/kill/2/",
         "attackers":[{{"character_id":3,"character_name":"Opponent","corporation_id":20,"corporation_name":"Hostile","alliance_id":null,"alliance_name":null,"faction_id":null,"ship":{{"type_id":200,"type_name":"Drake","ship_group_id":419,"ship_group_name":"Combat Battlecruiser"}},"damage_done":500,"final_blow":true}}]}}
      ]
    }}"#
    );
    serde_json::from_str(&value).unwrap()
}

#[test]
fn reconstructs_connected_engagement_and_all_dependent_totals() {
    let result = evaluate_battle_report(payload("\"side_overrides\":[],")).unwrap();
    let report = &result["report"];
    assert_eq!(report["killmail_count"], 2);
    assert_eq!(report["estimated_total_value"], 250000000.0);
    assert_eq!(report["duration_seconds"], 600);
    assert_eq!(report["timeline"].as_array().unwrap().len(), 2);
    assert_eq!(report["teams"][0]["ships_lost"], 1);
    assert_eq!(report["teams"][0]["efficiency"], 80.0);
    assert_eq!(
        report["teams"][0]["organizations"][0]["organization_id"],
        10
    );
    assert_eq!(report["participants"][0]["character_id"], 1);
    assert_eq!(report["participants"][0]["damage_done"], 700);
    assert_eq!(report["composition"][0]["ship_type_name"], "Rifter");
}

#[test]
fn manual_pilot_override_rebuilds_timeline_composition_and_teams() {
    let result = evaluate_battle_report(payload(
        "\"side_overrides\":[{\"character_id\":3,\"side\":2}],",
    ))
    .unwrap();
    let report = &result["report"];
    assert_eq!(report["side_overrides"]["3"], 2);
    assert_eq!(report["timeline"][0]["victim_side"], 2);
    assert!(report["teams"]
        .as_array()
        .unwrap()
        .iter()
        .any(|row| row["side"] == 2));
    assert!(report["composition"]
        .as_array()
        .unwrap()
        .iter()
        .any(|row| row["ship_type_id"] == 200 && row["side"] == 2));
}

#[test]
fn rejects_unknown_contract_schema() {
    let mut input = payload("\"side_overrides\":[],");
    input.schema_version = "future".to_string();
    assert!(evaluate_battle_report(input).is_err());
}
