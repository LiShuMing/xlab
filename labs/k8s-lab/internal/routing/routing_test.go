package routing

import (
	"testing"
)

func TestRoutingPoliciesDeterministicComparison(t *testing.T) {
	trace := GenerateWorkload(300, 42)
	cfg := DefaultClusterConfig()

	rr := Simulate(trace, cfg, PolicyRoundRobin)
	ll := Simulate(trace, cfg, PolicyLeastLoaded)
	pa := Simulate(trace, cfg, PolicyPrefixAware)
	pd := Simulate(trace, cfg, PolicyPDDisaggregated)

	// Determinism check: replaying the same trace produces bit-identical metrics.
	pa2 := Simulate(trace, cfg, PolicyPrefixAware)
	if pa != pa2 {
		t.Fatalf("non-deterministic simulation: %+v vs %+v", pa, pa2)
	}

	t.Logf("%-18s hit=%5.1f%% meanTTFT=%6.1fms p99TTFT=%6.1fms p99ITL=%5.1fms skew=%.2f",
		rr.Policy, rr.PrefixHitRate*100, rr.MeanTTFTMs, rr.P99TTFTMs, rr.P99DecodeITLMs, rr.LoadSkewRatio)
	t.Logf("%-18s hit=%5.1f%% meanTTFT=%6.1fms p99TTFT=%6.1fms p99ITL=%5.1fms skew=%.2f",
		ll.Policy, ll.PrefixHitRate*100, ll.MeanTTFTMs, ll.P99TTFTMs, ll.P99DecodeITLMs, ll.LoadSkewRatio)
	t.Logf("%-18s hit=%5.1f%% meanTTFT=%6.1fms p99TTFT=%6.1fms p99ITL=%5.1fms skew=%.2f",
		pa.Policy, pa.PrefixHitRate*100, pa.MeanTTFTMs, pa.P99TTFTMs, pa.P99DecodeITLMs, pa.LoadSkewRatio)
	t.Logf("%-18s hit=%5.1f%% meanTTFT=%6.1fms p99TTFT=%6.1fms p99ITL=%5.1fms skew=%.2f",
		pd.Policy, pd.PrefixHitRate*100, pd.MeanTTFTMs, pd.P99TTFTMs, pd.P99DecodeITLMs, pd.LoadSkewRatio)

	// 1. PrefixAware must achieve higher prefix cache hit rate and lower mean TTFT than RoundRobin.
	if pa.PrefixHitRate <= rr.PrefixHitRate {
		t.Fatalf("expected PrefixAware hit rate (%.3f) > RoundRobin (%.3f)", pa.PrefixHitRate, rr.PrefixHitRate)
	}
	if pa.MeanTTFTMs >= rr.MeanTTFTMs {
		t.Fatalf("expected PrefixAware mean TTFT (%.1fms) < RoundRobin (%.1fms)", pa.MeanTTFTMs, rr.MeanTTFTMs)
	}

	// 2. PDDisaggregated must isolate Decode P99 ITL better than colocated RoundRobin/LeastLoaded.
	if pd.P99DecodeITLMs >= rr.P99DecodeITLMs {
		t.Fatalf("expected PDDisaggregated P99 ITL (%.1fms) < colocated RoundRobin (%.1fms)",
			pd.P99DecodeITLMs, rr.P99DecodeITLMs)
	}
}
