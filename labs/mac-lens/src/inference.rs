//! Optional, explicitly configured, loopback-only Prometheus reader.
//! We never collect prompts, request bodies, model labels or authentication data.
use crate::model::{Inference, Rates};
use std::collections::{HashMap, HashSet};
use std::net::IpAddr;
use std::time::{Duration, Instant};

const METRICS: &[&str] = &[
    "vllm:num_requests_running",
    "vllm:num_requests_waiting",
    "vllm:kv_cache_usage_perc",
    "vllm:gpu_cache_usage_perc",
    "vllm:prompt_tokens_total",
    "vllm:generation_tokens_total",
    "vllm:time_to_first_token_seconds_sum",
    "vllm:time_to_first_token_seconds_count",
    "vllm:time_per_output_token_seconds_sum",
    "vllm:time_per_output_token_seconds_count",
    "vllm:request_time_per_output_token_seconds_sum",
    "vllm:request_time_per_output_token_seconds_count",
    "vllm:inter_token_latency_seconds_sum",
    "vllm:inter_token_latency_seconds_count",
];

type Series = HashMap<String, Vec<(String, f64)>>;

pub fn validate_url(url: &str) -> Result<(), String> {
    let uri: ureq::http::Uri = url.parse().map_err(|_| "invalid metrics URL")?;
    if uri.scheme_str() != Some("http")
        || uri.authority().is_none_or(|a| a.as_str().contains('@'))
        || uri.path_and_query().is_some_and(|p| p.query().is_some())
        || url.contains('#')
    {
        return Err("use a plain http loopback URL without credentials, query or fragment".into());
    }
    let host = uri.host().unwrap_or("").trim_matches(['[', ']']);
    let address: IpAddr = host
        .parse()
        .map_err(|_| "use a literal loopback IP, e.g. 127.0.0.1 (not DNS)")?;
    if !address.is_loopback() {
        return Err("metrics URL must point to this machine's loopback interface".into());
    }
    Ok(())
}

#[cfg(test)]
mod transport_tests {
    use super::*;
    use std::io::{Read, Write};
    use std::net::TcpListener;
    use std::thread;

    fn server(responses: Vec<String>) -> (String, thread::JoinHandle<()>) {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        listener.set_nonblocking(true).unwrap();
        let address = listener.local_addr().unwrap();
        let handle = thread::spawn(move || {
            for response in responses {
                let deadline = Instant::now() + Duration::from_secs(3);
                let mut stream = loop {
                    match listener.accept() {
                        Ok((stream, _)) => break stream,
                        Err(error)
                            if error.kind() == std::io::ErrorKind::WouldBlock
                                && Instant::now() < deadline =>
                        {
                            thread::sleep(Duration::from_millis(5))
                        }
                        Err(error) => panic!("synthetic server accept: {error}"),
                    }
                };
                stream
                    .set_read_timeout(Some(Duration::from_secs(1)))
                    .unwrap();
                let mut request = Vec::new();
                while !request.ends_with(b"\r\n\r\n") && request.len() < 4096 {
                    let mut byte = [0];
                    if stream.read(&mut byte).unwrap_or(0) == 0 {
                        break;
                    }
                    request.push(byte[0]);
                }
                assert!(request.starts_with(b"GET /metrics HTTP/1.1"));
                let _ = stream.write_all(response.as_bytes());
            }
        });
        (format!("http://{address}/metrics"), handle)
    }

    fn ok(body: &str) -> String {
        format!(
            "HTTP/1.1 200 OK\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
            body.len()
        )
    }

    #[test]
    fn real_http_scrapes_then_rates() {
        let body = "vllm:num_requests_running 3\nvllm:kv_cache_usage_perc 0.7\nvllm:generation_tokens_total 100\n";
        let (url, handle) = server(vec![ok(body), ok(&body.replace("100", "120"))]);
        let mut reader = Reader::new(Some(url)).unwrap();
        let first = reader.sample();
        assert!(first.connected);
        assert_eq!(first.running, Some(3.0));
        assert_eq!(first.kv_percent, Some(70.0));
        assert_eq!(first.generation_tps, None);
        assert!(reader.sample().generation_tps.unwrap() > 0.0);
        handle.join().unwrap();
    }

    #[test]
    fn body_bound_and_http_failure() {
        for response in [
            ok(&"x".repeat(512 * 1024 + 1)),
            "HTTP/1.1 500 Error\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".into(),
        ] {
            let (url, handle) = server(vec![response]);
            let sample = Reader::new(Some(url)).unwrap().sample();
            assert!(!sample.connected);
            assert!(sample.generation_tps.is_none());
            handle.join().unwrap();
        }
    }

    #[test]
    fn redirects_never_contact_the_destination() {
        let destination = TcpListener::bind("127.0.0.1:0").unwrap();
        destination.set_nonblocking(true).unwrap();
        let response = format!("HTTP/1.1 302 Found\r\nLocation: http://{}/metrics\r\nContent-Length: 0\r\nConnection: close\r\n\r\n", destination.local_addr().unwrap());
        let (url, handle) = server(vec![response]);
        assert!(!Reader::new(Some(url)).unwrap().sample().connected);
        assert!(
            matches!(destination.accept(), Err(e) if e.kind() == std::io::ErrorKind::WouldBlock)
        );
        handle.join().unwrap();
    }

    #[test]
    fn new_tpot_and_itl_remain_distinct() {
        let first = "vllm:request_time_per_output_token_seconds_sum 4\nvllm:request_time_per_output_token_seconds_count 2\nvllm:inter_token_latency_seconds_sum 2\nvllm:inter_token_latency_seconds_count 4\nvllm:time_per_output_token_seconds_sum 100\nvllm:time_per_output_token_seconds_count 2\nvllm:kv_cache_usage_perc 0.6\nvllm:gpu_cache_usage_perc 0.1\n";
        let second = first
            .replace("sum 4", "sum 8")
            .replace("count 2", "count 4")
            .replace("sum 2\n", "sum 10\n")
            .replace("latency_seconds_count 4", "latency_seconds_count 20");
        let mut reader = Reader::new(None).unwrap();
        let at = Instant::now();
        reader.update_from_text(first, at).unwrap();
        let s = reader
            .update_from_text(&second, at + Duration::from_secs(2))
            .unwrap();
        assert_eq!(s.tpot_seconds, Some(2.0));
        assert_eq!(s.itl_seconds, Some(0.5));
        assert_eq!(s.kv_percent, Some(60.0));
        assert!(reader.update_from_text("vllm:num_requests_running{a=\"1\"} 1e308\nvllm:num_requests_running{a=\"2\"} 1e308", at).is_err());
    }
}

fn parse(text: &str) -> Result<Series, String> {
    let mut result: Series = HashMap::new();
    for line in text
        .lines()
        .map(str::trim)
        .filter(|l| !l.is_empty() && !l.starts_with('#'))
    {
        let end = line
            .find(|c: char| c == '{' || c.is_whitespace())
            .unwrap_or(line.len());
        let name = &line[..end];
        if !METRICS.contains(&name) {
            continue;
        }
        let rest = &line[end..];
        let (identity, value_text) = if rest.starts_with('{') {
            let (mut quoted, mut escaped, mut close) = (false, false, None);
            for (index, c) in rest.char_indices().skip(1) {
                if escaped {
                    escaped = false;
                    continue;
                }
                if quoted && c == '\\' {
                    escaped = true;
                    continue;
                }
                if c == '"' {
                    quoted = !quoted;
                }
                if c == '}' && !quoted {
                    close = Some(index);
                    break;
                }
            }
            let close = close.ok_or("malformed recognized Prometheus labels")?;
            (format!("{name}{}", &rest[..=close]), &rest[close + 1..])
        } else {
            (name.to_string(), rest)
        };
        let value: f64 = value_text
            .split_whitespace()
            .next()
            .ok_or("missing metric value")?
            .parse()
            .map_err(|_| "invalid metric value")?;
        if !value.is_finite() || value < 0.0 {
            return Err("nonfinite/negative recognized metric".into());
        }
        if name.ends_with("usage_perc") && value > 1.0 {
            return Err("KV cache gauge is outside [0,1]".into());
        }
        let entries = result.entry(name.to_string()).or_default();
        if entries.iter().any(|(key, _)| key == &identity) {
            return Err("duplicate metric series".into());
        }
        entries.push((identity, value));
    }
    if result.is_empty() {
        return Err("endpoint has no supported vLLM metrics".into());
    }
    Ok(result)
}

pub struct Reader {
    url: Option<String>,
    agent: ureq::Agent,
    rates: Rates,
}

impl Reader {
    pub fn new(url: Option<String>) -> Result<Self, String> {
        if let Some(url) = &url {
            validate_url(url)?;
        }
        let agent = ureq::Agent::config_builder()
            .proxy(None)
            .max_redirects(0)
            .timeout_global(Some(Duration::from_millis(800)))
            .build()
            .into();
        Ok(Self {
            url,
            agent,
            rates: Rates::default(),
        })
    }

    pub fn sample(&mut self) -> Inference {
        let Some(url) = &self.url else {
            return Inference {
                reason: "Not configured; use --metrics-url http://127.0.0.1:8000/metrics".into(),
                ..Default::default()
            };
        };
        // Response body has a hard size bound. No redirects, proxies or API keys.
        let response = self.agent.get(url).call().and_then(|mut response| {
            if response.status() != 200 {
                return Err(ureq::Error::StatusCode(response.status().as_u16()));
            }
            response
                .body_mut()
                .with_config()
                .limit(512 * 1024)
                .read_to_string()
        });
        match response {
            Ok(text) => match self.update_from_text(&text, Instant::now()) {
                Ok(sample) => sample,
                Err(reason) => {
                    self.rates.clear();
                    Inference {
                        reason,
                        ..Default::default()
                    }
                }
            },
            Err(_) => {
                self.rates.clear();
                Inference {
                    reason: "Metrics unavailable: HTTP error, 800ms timeout or response >512 KiB"
                        .into(),
                    ..Default::default()
                }
            }
        }
    }

    fn update_from_text(&mut self, text: &str, now: Instant) -> Result<Inference, String> {
        let metrics = parse(text)?;
        let gauge = |key: &str| {
            metrics
                .get(key)
                .map(|rows| rows.iter().map(|(_, value)| value).sum())
        };
        let kv = metrics
            .get("vllm:kv_cache_usage_perc")
            .or_else(|| metrics.get("vllm:gpu_cache_usage_perc"))
            .map(|rows| rows.iter().map(|(_, value)| *value).fold(0.0, f64::max) * 100.0);
        // Difference each label series separately so a reset in one worker cannot
        // be hidden by another worker's increasing counter. Any new/reset series
        // makes the aggregate unavailable for one observation window.
        let mut present = HashSet::new();
        let mut deltas = HashMap::new();
        for (name, rows) in &metrics {
            if !name.ends_with("_total") && !name.ends_with("_sum") && !name.ends_with("_count") {
                continue;
            }
            let values: Vec<_> = rows
                .iter()
                .map(|(identity, value)| {
                    let key = format!("metrics:{identity}");
                    present.insert(key.clone());
                    self.rates.observe(&key, *value, now)
                })
                .collect();
            let sum = values
                .into_iter()
                .collect::<Option<Vec<f64>>>()
                .map(|v| v.iter().sum::<f64>());
            deltas.insert(name.as_str(), sum);
        }
        self.rates.retain("metrics:", &present);
        let rate = |name: &str| deltas.get(name).copied().flatten();
        let mean = |sum, count| {
            let count = rate(count)?;
            (count > 0.0)
                .then(|| rate(sum).map(|value| value / count))
                .flatten()
        };
        let (tpot_sum, tpot_count) =
            if metrics.contains_key("vllm:request_time_per_output_token_seconds_sum") {
                (
                    "vllm:request_time_per_output_token_seconds_sum",
                    "vllm:request_time_per_output_token_seconds_count",
                )
            } else {
                (
                    "vllm:time_per_output_token_seconds_sum",
                    "vllm:time_per_output_token_seconds_count",
                )
            };
        let sample = Inference {
            connected: true,
            reason: "vLLM gauges; counter rates and histogram MEANS over successful scrape windows (not p95/p99)".into(),
            running: gauge("vllm:num_requests_running"), waiting: gauge("vllm:num_requests_waiting"),
            kv_percent: kv, prompt_tps: rate("vllm:prompt_tokens_total"),
            generation_tps: rate("vllm:generation_tokens_total"),
            ttft_seconds: mean("vllm:time_to_first_token_seconds_sum", "vllm:time_to_first_token_seconds_count"),
            tpot_seconds: mean(tpot_sum, tpot_count),
            itl_seconds: mean("vllm:inter_token_latency_seconds_sum", "vllm:inter_token_latency_seconds_count"),
        };
        if [
            sample.running,
            sample.waiting,
            sample.prompt_tps,
            sample.generation_tps,
            sample.ttft_seconds,
            sample.tpot_seconds,
            sample.itl_seconds,
        ]
        .into_iter()
        .flatten()
        .any(|v| !v.is_finite())
        {
            return Err("metric aggregation overflow".into());
        }
        Ok(sample)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn endpoint_boundaries() {
        for url in ["http://127.0.0.1:8000/metrics", "http://[::1]:8000/metrics"] {
            assert!(validate_url(url).is_ok());
        }
        for url in [
            "https://127.0.0.1/metrics",
            "http://example.com/metrics",
            "http://localhost/metrics",
            "http://127.0.0.1@evil.test/metrics",
            "http://u:p@127.0.0.1/metrics",
            "http://127.0.0.1/metrics?key=a",
            "http://127.0.0.1/#fragment",
        ] {
            assert!(validate_url(url).is_err(), "{url}");
        }
    }

    #[test]
    fn counters_mean_latency_and_aliases() {
        let mut reader = Reader::new(None).unwrap();
        let at = Instant::now();
        let base = "vllm:generation_tokens_total{model_name=\"test}\"} 100\nvllm:time_to_first_token_seconds_sum 4\nvllm:time_to_first_token_seconds_count 2\nvllm:gpu_cache_usage_perc 0.5\n";
        let first = reader.update_from_text(base, at).unwrap();
        assert_eq!(first.generation_tps, None);
        assert_eq!(first.kv_percent, Some(50.0));
        let next = base
            .replace(" 100", " 140")
            .replace("sum 4", "sum 8")
            .replace("count 2", "count 4");
        let next = reader
            .update_from_text(&next, at + Duration::from_secs(2))
            .unwrap();
        assert_eq!(next.generation_tps, Some(20.0));
        assert_eq!(next.ttft_seconds, Some(2.0));
        let reset = reader
            .update_from_text(base, at + Duration::from_secs(3))
            .unwrap();
        assert_eq!(reset.generation_tps, None);
    }

    #[test]
    fn absent_invalid_and_multi_series_reset() {
        assert!(parse("unrelated 1").is_err());
        for input in [
            "vllm:generation_tokens_total NaN",
            "vllm:num_requests_running -1",
            "vllm:kv_cache_usage_perc 20",
            "vllm:num_requests_running{a=\"x\" 1",
        ] {
            assert!(parse(input).is_err());
        }
        let mut reader = Reader::new(None).unwrap();
        let a = "vllm:generation_tokens_total{worker=\"a\"} 100\nvllm:generation_tokens_total{worker=\"b\"} 100\n";
        let at = Instant::now();
        reader.update_from_text(a, at).unwrap();
        let b = a
            .replace("a\"} 100", "a\"} 1")
            .replace("b\"} 100", "b\"} 1000");
        assert_eq!(
            reader
                .update_from_text(&b, at + Duration::from_secs(1))
                .unwrap()
                .generation_tps,
            None
        );
    }
}
