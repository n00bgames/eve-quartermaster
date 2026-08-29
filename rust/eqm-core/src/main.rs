use std::{env, fs, io, process};

use eqm_core::analytics_summary::{evaluate_analytics_summary, AnalyticsSummaryInput};
use eqm_core::bounty_analytics::{evaluate_bounty_analytics, BountyAnalyticsInput};
use eqm_core::colony_simulation::{simulate_colony, ColonySimulationInput};
use eqm_core::fitting_math::{evaluate_fitting_math, FittingMathInput};
use eqm_core::fitting_resources::{evaluate_fitting_resources, FittingResourcesInput};
use eqm_core::fitting_stats::{evaluate_fitting_stats, FittingStatsInput};
use eqm_core::jump_route::{evaluate_jump_route, JumpRouteInput};
use eqm_core::killboard_analytics::{evaluate_killboard_analytics, KillboardAnalyticsInput};
use eqm_core::pi_shortage::{build_planetary_shortage_report, PlanetaryIndustryPayload};
use eqm_core::settlement_math::{evaluate_settlement_math, SettlementMathInput};

fn value_after(args: &[String], flag: &str) -> Option<String> {
    args.windows(2)
        .find(|pair| pair[0] == flag)
        .map(|pair| pair[1].clone())
}

fn usage() -> ! {
    eprintln!(
        "Usage:\n  eqm-core pi-shortage --input <payload.json> [--target-type-id <id>] [--generated-at <ISO-8601>]\n  eqm-core colony-simulation --input <payload.json>\n  eqm-core fitting-math --input <payload.json>\n  eqm-core fitting-resources --input <payload.json>\n  eqm-core fitting-stats --input <payload.json>\n  eqm-core analytics-summary --input <payload.json>\n  eqm-core bounty-analytics --input <payload.json>\n  eqm-core jump-route --input <payload.json>\n  eqm-core settlement-math --input <payload.json>\n  eqm-core killboard-analytics --input <payload.json>"
    );
    process::exit(2);
}

fn run() -> Result<(), String> {
    let args: Vec<String> = env::args().skip(1).collect();
    let command = args.first().map(String::as_str).unwrap_or_else(|| usage());
    let input_path =
        value_after(&args, "--input").ok_or_else(|| "--input is required".to_string())?;
    let input_text = if input_path == "-" {
        io::read_to_string(io::stdin())
            .map_err(|error| format!("unable to read standard input: {error}"))?
    } else {
        fs::read_to_string(&input_path)
            .map_err(|error| format!("unable to read {input_path}: {error}"))?
    };
    let output = match command {
        "pi-shortage" => {
            let target_type_id = value_after(&args, "--target-type-id")
                .map(|value| {
                    value
                        .parse::<u64>()
                        .map_err(|_| format!("invalid target type ID: {value}"))
                })
                .transpose()?;
            let payload: PlanetaryIndustryPayload = serde_json::from_str(&input_text)
                .map_err(|error| format!("invalid PI payload: {error}"))?;
            let generated_at =
                value_after(&args, "--generated-at").unwrap_or_else(|| payload.as_of.clone());
            serde_json::to_value(build_planetary_shortage_report(
                &payload,
                target_type_id,
                &generated_at,
            ))
        }
        "colony-simulation" => {
            let payload: ColonySimulationInput = serde_json::from_str(&input_text)
                .map_err(|error| format!("invalid colony simulation payload: {error}"))?;
            serde_json::to_value(simulate_colony(payload)?)
        }
        "fitting-math" => {
            let payload: FittingMathInput = serde_json::from_str(&input_text)
                .map_err(|error| format!("invalid fitting math payload: {error}"))?;
            serde_json::to_value(evaluate_fitting_math(payload)?)
        }
        "fitting-resources" => {
            let payload: FittingResourcesInput = serde_json::from_str(&input_text)
                .map_err(|error| format!("invalid fitting resources payload: {error}"))?;
            serde_json::to_value(evaluate_fitting_resources(payload)?)
        }
        "fitting-stats" => {
            let payload: FittingStatsInput = serde_json::from_str(&input_text)
                .map_err(|error| format!("invalid fitting stats payload: {error}"))?;
            serde_json::to_value(evaluate_fitting_stats(payload)?)
        }
        "analytics-summary" => {
            let payload: AnalyticsSummaryInput = serde_json::from_str(&input_text)
                .map_err(|error| format!("invalid analytics summary payload: {error}"))?;
            serde_json::to_value(evaluate_analytics_summary(payload)?)
        }
        "bounty-analytics" => {
            let payload: BountyAnalyticsInput = serde_json::from_str(&input_text)
                .map_err(|error| format!("invalid bounty analytics payload: {error}"))?;
            serde_json::to_value(evaluate_bounty_analytics(payload)?)
        }
        "jump-route" => {
            let payload: JumpRouteInput = serde_json::from_str(&input_text)
                .map_err(|error| format!("invalid jump route payload: {error}"))?;
            serde_json::to_value(evaluate_jump_route(payload)?)
        }
        "settlement-math" => {
            let payload: SettlementMathInput = serde_json::from_str(&input_text)
                .map_err(|error| format!("invalid settlement math payload: {error}"))?;
            serde_json::to_value(evaluate_settlement_math(payload)?)
        }
        "killboard-analytics" => {
            let payload: KillboardAnalyticsInput = serde_json::from_str(&input_text)
                .map_err(|error| format!("invalid killboard analytics payload: {error}"))?;
            serde_json::to_value(evaluate_killboard_analytics(payload)?)
        }
        _ => usage(),
    }
    .map_err(|error| format!("unable to serialize report: {error}"))?;
    println!("{}", serde_json::to_string_pretty(&output).unwrap());
    Ok(())
}

fn main() {
    if let Err(error) = run() {
        eprintln!("eqm-core: {error}");
        process::exit(1);
    }
}
