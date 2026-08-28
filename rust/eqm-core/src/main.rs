use std::{env, fs, process};

use eqm_core::pi_shortage::{build_planetary_shortage_report, PlanetaryIndustryPayload};

fn value_after(args: &[String], flag: &str) -> Option<String> {
    args.windows(2)
        .find(|pair| pair[0] == flag)
        .map(|pair| pair[1].clone())
}

fn usage() -> ! {
    eprintln!(
        "Usage: eqm-core pi-shortage --input <payload.json> [--target-type-id <id>] [--generated-at <ISO-8601>]"
    );
    process::exit(2);
}

fn run() -> Result<(), String> {
    let args: Vec<String> = env::args().skip(1).collect();
    if args.first().map(String::as_str) != Some("pi-shortage") {
        usage();
    }

    let input_path = value_after(&args, "--input").ok_or_else(|| "--input is required".to_string())?;
    let target_type_id = value_after(&args, "--target-type-id")
        .map(|value| value.parse::<u64>().map_err(|_| format!("invalid target type ID: {value}")))
        .transpose()?;
    let input_text = fs::read_to_string(&input_path)
        .map_err(|error| format!("unable to read {input_path}: {error}"))?;
    let payload: PlanetaryIndustryPayload = serde_json::from_str(&input_text)
        .map_err(|error| format!("invalid PI payload: {error}"))?;
    let generated_at = value_after(&args, "--generated-at").unwrap_or_else(|| payload.as_of.clone());
    let report = build_planetary_shortage_report(&payload, target_type_id, &generated_at);
    println!(
        "{}",
        serde_json::to_string_pretty(&report)
            .map_err(|error| format!("unable to serialize report: {error}"))?
    );
    Ok(())
}

fn main() {
    if let Err(error) = run() {
        eprintln!("eqm-core: {error}");
        process::exit(1);
    }
}
