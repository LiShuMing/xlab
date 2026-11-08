use serde_json::Value;
use std::path::PathBuf;
use std::process::Command;

struct Directory(PathBuf);
impl Directory {
    fn new() -> Self {
        let path = std::env::temp_dir().join(format!(
            "kernel-lens-cli-test-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir(&path).unwrap();
        Self(path)
    }
}
impl Drop for Directory {
    fn drop(&mut self) {
        std::fs::remove_dir_all(&self.0).unwrap();
    }
}
fn command() -> Command {
    Command::new(env!("CARGO_BIN_EXE_kernel-lens"))
}
fn benchmark(kind: &str) -> Value {
    let output = command()
        .args([
            "--benchmark",
            kind,
            "--bench-rounds",
            "1",
            "--bench-duration-ms",
            "100",
            "--bench-size-mib",
            "1",
        ])
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let report: Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(report["kind"], kind);
    assert_eq!(report["workload_version"], 1);
    assert_eq!(report["config"]["rounds"], 1);
    assert!(!report["environment"].as_array().unwrap().is_empty());
    assert!(!report["observations_after"].as_array().unwrap().is_empty());
    let measures = report["measurements"].as_array().unwrap();
    assert!(!measures.is_empty());
    for measure in measures {
        assert!(measure["median"].as_f64().unwrap() > 0.0);
        assert_eq!(measure["values"].as_array().unwrap().len(), 1);
    }
    report
}
#[test]
fn short_cpu_and_memory_workers_return_context_and_rounds() {
    benchmark("cpu");
    benchmark("memory");
}
#[test]
fn scheduler_and_loopback_workers_complete_and_report_their_scope() {
    let scheduler = benchmark("scheduler");
    assert_eq!(scheduler["measurements"][0]["unit"], "µs/roundtrip");
    let tcp = benchmark("tcp-loopback");
    assert!(tcp["notes"][0].as_str().unwrap().contains("物理网卡"));
}
#[test]
fn file_test_cleans_only_its_own_files() {
    let directory = Directory::new();
    let protected = directory.0.join("preserve-me");
    std::fs::write(&protected, "keep").unwrap();
    let output = command()
        .args([
            "--benchmark",
            "file-io",
            "--bench-rounds",
            "2",
            "--bench-size-mib",
            "1",
            "--bench-dir",
        ])
        .arg(&directory.0)
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let report: Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(report["measurements"].as_array().unwrap().len(), 2);
    assert_eq!(
        report["measurements"][0]["values"]
            .as_array()
            .unwrap()
            .len(),
        2
    );
    assert_eq!(std::fs::read_to_string(&protected).unwrap(), "keep");
    assert_eq!(std::fs::read_dir(&directory.0).unwrap().count(), 1);
}
#[test]
fn invalid_configuration_is_rejected_before_work() {
    for args in [
        vec!["--benchmark", "file-io"],
        vec!["--benchmark", "unknown"],
        vec!["--benchmark", "cpu", "--bench-size-mib", "0"],
        vec!["--summary", "--snapshot"],
    ] {
        let output = command().args(args).output().unwrap();
        assert!(!output.status.success());
        assert!(output.stdout.is_empty());
    }
}
