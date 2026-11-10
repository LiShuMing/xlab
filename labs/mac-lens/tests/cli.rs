use std::process::Command;

fn binary() -> Command {
    Command::new(env!("CARGO_BIN_EXE_mac-lens"))
}

#[test]
fn help_and_nonterminal_exit_cleanly() {
    let help = binary().arg("--help").output().unwrap();
    assert!(help.status.success());
    assert!(String::from_utf8_lossy(&help.stdout).contains("--metrics-url"));
    let not_a_terminal = binary().output().unwrap();
    assert!(!not_a_terminal.status.success());
    assert!(String::from_utf8_lossy(&not_a_terminal.stderr).contains("interactive terminal"));
    assert!(
        !not_a_terminal.stdout.contains(&27),
        "no alternate-screen escape sequences on stdout"
    );
}

#[test]
fn headless_warmup_then_rates_without_gpu_or_exports() {
    let output = binary()
        .args([
            "--snapshot",
            "--samples",
            "2",
            "--interval-ms",
            "500",
            "--no-gpu",
        ])
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let samples: Vec<serde_json::Value> = String::from_utf8(output.stdout)
        .unwrap()
        .lines()
        .map(|line| serde_json::from_str(line).unwrap())
        .collect();
    assert_eq!(samples.len(), 2);
    assert_eq!(samples[0]["schema_version"], 1);
    assert!(samples[1]["sequence"].as_u64().unwrap() > samples[0]["sequence"].as_u64().unwrap());
    assert!(samples[0]["gpu"]["active_percent"].is_null());
    assert!(samples[0]["memory"]["total"].as_u64().unwrap() > 0);
    let first = samples[0]["networks"].as_array().unwrap();
    assert!(first.iter().all(|n| n["rx_bps"].is_null()));
    let second = samples[1]["networks"].as_array().unwrap();
    assert!(second.iter().any(|n| n["rx_bps"].is_number()) || second.is_empty());
    assert!(!samples[0]["inference"]["connected"].as_bool().unwrap());
}

#[test]
fn invalid_options_fail_before_any_sampling() {
    for args in [
        vec!["--metrics-url", "http://u:p@127.0.0.1/metrics"],
        vec!["--interval-ms", "0"],
        vec!["--snapshot", "--samples", "0"],
    ] {
        let output = binary().args(args).output().unwrap();
        assert!(!output.status.success());
        assert!(output.stdout.is_empty());
    }
}
