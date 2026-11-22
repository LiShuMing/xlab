// Package routing implements a deterministic trace-replay simulator for
// multi-instance LLM serving clusters, comparing four routing architectures:
//
//   - RoundRobin: blind cyclic dispatch (ignores queue load and KV prefix cache).
//   - LeastLoaded: dispatches to the instance with lowest current queue work
//     (good balance, but thrashes prefix KV cache across replicas).
//   - PrefixAware (KV-Cache-Aware): tracks per-replica prefix cache residency
//     with LRU eviction and routes shared-prefix requests to warm replicas
//     unless load skew exceeds a configurable overload threshold.
//   - PDDisaggregated (Prefill/Decode Disaggregation): separates compute-heavy
//     Prefill workers from latency-sensitive Decode workers, transferring KV
//     blocks over an α-β interconnect model so long prefills never stall
//     in-flight decode ITL.
//
// What it teaches:
//   - Why blind load balancing destroys Prefix Caching hit rate in multi-replica
//     serving, and why naive sticky routing causes hot-spot load skew.
//   - Why separating Prefill and Decode pools isolates decode P99 ITL from long
//     prompt bursts, and how KV transfer bandwidth constrains PD disaggregation.
//
// Simplifications:
//   - Discrete-event simulation with deterministic linear compute/bandwidth
//     service-time models (no real GPU kernels or TCP sockets).
package routing

import (
	"math"
	"math/rand"
	"sort"
)

// Policy identifies a cluster request routing strategy.
type Policy string

const (
	PolicyRoundRobin      Policy = "round_robin"
	PolicyLeastLoaded     Policy = "least_loaded"
	PolicyPrefixAware     Policy = "prefix_aware"
	PolicyPDDisaggregated Policy = "pd_disaggregated"
)

// Request represents one synthetic LLM serving request in a replay trace.
type Request struct {
	ID           int
	ArrivalMs    float64
	PrefixKey    string // shared system-prompt / session prefix identifier
	PrefixTokens int    // reusable prefix token count
	SuffixTokens int    // unique user query tokens
	OutputTokens int    // decode tokens to generate
}

// ClusterConfig configures the simulated replica pool and hardware rates.
type ClusterConfig struct {
	NumReplicas         int     // total GPU instances (for PD: split into PrefillReplicas + DecodeReplicas)
	PrefillReplicas     int     // used only for PolicyPDDisaggregated
	PrefillTokPerMs     float64 // prefill compute throughput per replica (e.g. 8.0 tok/ms = 8000 tok/s)
	DecodeMsPerToken    float64 // base decode ITL per token (e.g. 12.0 ms)
	CacheCapacityBlocks int     // per-replica prefix cache capacity (1 block = 64 tokens)
	MaxSkewMs           float64 // overload guard for PrefixAware (fallback to LeastLoaded if warmer node is too busy)
	KVTransferAlphaMs   float64 // fixed KV transfer setup latency for PD disaggregation
	KVTransferMsPerTok  float64 // per-token KV transfer time over NVLink/RDMA
}

// DefaultClusterConfig returns a realistic 4-instance serving cluster profile.
func DefaultClusterConfig() ClusterConfig {
	return ClusterConfig{
		NumReplicas:         4,
		PrefillReplicas:     2,
		PrefillTokPerMs:     6.0,   // 6000 tok/s prefill per GPU
		DecodeMsPerToken:    10.0,  // 10 ms base ITL
		CacheCapacityBlocks: 64,    // 64 * 64 = 4096 cached prefix tokens per replica
		MaxSkewMs:           250.0, // allow up to 250ms queue skew to preserve prefix hit
		KVTransferAlphaMs:   1.5,   // 1.5ms transfer handshake
		KVTransferMsPerTok:  0.015, // ~15us/token KV transfer (RDMA/NVLink)
	}
}

// SimResult aggregates end-to-end serving metrics for one routing policy.
type SimResult struct {
	Policy          Policy
	NumRequests     int
	PrefixHitRate   float64 // fraction of requests hitting cached prefix
	MeanTTFTMs      float64
	P99TTFTMs       float64
	MeanDecodeITLMs float64
	P99DecodeITLMs  float64
	LoadSkewRatio   float64 // max_replica_requests / mean_replica_requests
}

// GenerateWorkload creates a deterministic multi-tenant trace mixing hot shared
// system prompts (Zipf-like skew across a few prefix tenants) and occasional
// long-prompt bursts.
func GenerateWorkload(numRequests int, seed int64) []Request {
	rng := rand.New(rand.NewSource(seed))
	hotPrefixes := []string{"sys-coding", "sys-sql-agent", "sys-rag-docs", "sys-chat"}
	reqs := make([]Request, numRequests)
	nowMs := 0.0
	for i := range numRequests {
		if i > 0 {
			// Poisson arrivals at ~12 req/s (~83ms mean inter-arrival).
			nowMs += rng.ExpFloat64() * 83.0
		}
		var prefixKey string
		var prefixToks, suffixToks int
		r := rng.Float64()
		switch {
		case r < 0.70:
			// Shared hot prefix (multi-turn / system prompt reuse).
			prefixKey = hotPrefixes[rng.Intn(len(hotPrefixes))]
			prefixToks = 512
			suffixToks = 32 + rng.Intn(96)
		case r < 0.88:
			// Occasional long-prompt prefill burst (stresses colocated decode ITL!).
			prefixKey = hotPrefixes[rng.Intn(2)]
			prefixToks = 1024
			suffixToks = 512 + rng.Intn(512)
		default:
			// One-hit unique prompt (no reuse).
			prefixKey = ""
			prefixToks = 0
			suffixToks = 128 + rng.Intn(256)
		}
		reqs[i] = Request{
			ID:           i,
			ArrivalMs:    nowMs,
			PrefixKey:    prefixKey,
			PrefixTokens: prefixToks,
			SuffixTokens: suffixToks,
			OutputTokens: 24 + rng.Intn(40),
		}
	}
	return reqs
}

type lruCache struct {
	capBlocks int
	used      int
	entries   map[string]int // prefixKey -> blocks
	order     []string       // oldest at index 0, newest at end
}

func newLRUCache(capBlocks int) *lruCache {
	return &lruCache{capBlocks: capBlocks, entries: make(map[string]int)}
}

func (c *lruCache) has(key string) bool {
	if key == "" {
		return false
	}
	_, ok := c.entries[key]
	if ok {
		c.touch(key)
	}
	return ok
}

func (c *lruCache) touch(key string) {
	for i, k := range c.order {
		if k == key {
			c.order = append(c.order[:i], c.order[i+1:]...)
			c.order = append(c.order, key)
			return
		}
	}
}

func (c *lruCache) put(key string, blocks int) {
	if key == "" || blocks <= 0 || blocks > c.capBlocks {
		return
	}
	if _, exists := c.entries[key]; exists {
		c.touch(key)
		return
	}
	for c.used+blocks > c.capBlocks && len(c.order) > 0 {
		victim := c.order[0]
		c.order = c.order[1:]
		c.used -= c.entries[victim]
		delete(c.entries, victim)
	}
	c.entries[key] = blocks
	c.order = append(c.order, key)
	c.used += blocks
}

type replica struct {
	freeAtMs   float64
	served     int
	cache      *lruCache
	prefillEnd []float64 // tracks recent prefill busy spikes overlapping decode
}

// Simulate replays `trace` under `policy` and returns deterministic serving metrics.
func Simulate(trace []Request, cfg ClusterConfig, policy Policy) SimResult {
	if len(trace) == 0 {
		return SimResult{Policy: policy}
	}
	if policy == PolicyPDDisaggregated {
		return simulatePD(trace, cfg)
	}

	replicas := make([]*replica, cfg.NumReplicas)
	for i := range replicas {
		replicas[i] = &replica{cache: newLRUCache(cfg.CacheCapacityBlocks)}
	}

	ttfts := make([]float64, 0, len(trace))
	itls := make([]float64, 0, len(trace))
	hits := 0
	rrIdx := 0

	for _, req := range trace {
		var chosen int
		switch policy {
		case PolicyRoundRobin:
			chosen = rrIdx % cfg.NumReplicas
			rrIdx++
		case PolicyLeastLoaded:
			chosen = pickLeastLoaded(replicas, req.ArrivalMs)
		case PolicyPrefixAware:
			chosen = pickPrefixAware(replicas, req, cfg.MaxSkewMs)
		default:
			chosen = pickLeastLoaded(replicas, req.ArrivalMs)
		}

		rep := replicas[chosen]
		rep.served++

		hit := req.PrefixKey != "" && rep.cache.has(req.PrefixKey)
		if hit {
			hits++
		}
		computeTokens := req.SuffixTokens
		if !hit {
			computeTokens += req.PrefixTokens
		}

		// Queue wait on colocated replica + prefill duration.
		queueWait := math.Max(0.0, rep.freeAtMs-req.ArrivalMs)
		prefillMs := float64(computeTokens) / cfg.PrefillTokPerMs
		ttft := queueWait + prefillMs

		// Colocated prefill-decode interference: concurrent long prefills on the
		// same GPU stall in-flight decode steps proportionally to queued prefill work.
		interference := 0.0
		if queueWait > 0 {
			interference = math.Min(45.0, queueWait*0.18)
		}
		effITL := cfg.DecodeMsPerToken + interference

		// Advance replica busy horizon (prefill blocks the GPU exclusively; decode
		// consumes a smaller fraction when batched).
		startMs := math.Max(req.ArrivalMs, rep.freeAtMs)
		decodeShareMs := float64(req.OutputTokens) * cfg.DecodeMsPerToken * 0.25
		rep.freeAtMs = startMs + prefillMs + decodeShareMs

		if req.PrefixKey != "" {
			blocks := (req.PrefixTokens + 63) / 64
			rep.cache.put(req.PrefixKey, blocks)
		}

		ttfts = append(ttfts, ttft)
		itls = append(itls, effITL)
	}

	return buildResult(policy, len(trace), hits, ttfts, itls, replicas)
}

func simulatePD(trace []Request, cfg ClusterConfig) SimResult {
	pCount := max(1, min(cfg.PrefillReplicas, cfg.NumReplicas-1))
	dCount := max(1, cfg.NumReplicas-pCount)

	prefillPool := make([]*replica, pCount)
	for i := range prefillPool {
		prefillPool[i] = &replica{cache: newLRUCache(cfg.CacheCapacityBlocks)}
	}
	decodePool := make([]*replica, dCount)
	for i := range decodePool {
		decodePool[i] = &replica{cache: newLRUCache(0)}
	}

	ttfts := make([]float64, 0, len(trace))
	itls := make([]float64, 0, len(trace))
	hits := 0

	for _, req := range trace {
		// 1. Route prefill using PrefixAware across the dedicated Prefill pool.
		pIdx := pickPrefixAware(prefillPool, req, cfg.MaxSkewMs)
		pRep := prefillPool[pIdx]
		pRep.served++

		hit := req.PrefixKey != "" && pRep.cache.has(req.PrefixKey)
		if hit {
			hits++
		}
		computeTokens := req.SuffixTokens
		if !hit {
			computeTokens += req.PrefixTokens
		}

		pQueueWait := math.Max(0.0, pRep.freeAtMs-req.ArrivalMs)
		prefillMs := float64(computeTokens) / cfg.PrefillTokPerMs
		pStart := math.Max(req.ArrivalMs, pRep.freeAtMs)
		pRep.freeAtMs = pStart + prefillMs
		if req.PrefixKey != "" {
			pRep.cache.put(req.PrefixKey, (req.PrefixTokens+63)/64)
		}

		// 2. Transfer KV cache over α-β interconnect to least-loaded Decode worker.
		totalPromptToks := req.PrefixTokens + req.SuffixTokens
		transferMs := cfg.KVTransferAlphaMs + float64(totalPromptToks)*cfg.KVTransferMsPerTok
		decodeArriveMs := pStart + prefillMs + transferMs

		dIdx := pickLeastLoaded(decodePool, decodeArriveMs)
		dRep := decodePool[dIdx]
		dRep.served++

		// Decode pool sees ZERO prefill interference: ITL stays near base decode latency!
		dQueueWait := math.Max(0.0, dRep.freeAtMs-decodeArriveMs)
		dStart := math.Max(decodeArriveMs, dRep.freeAtMs)
		dRep.freeAtMs = dStart + float64(req.OutputTokens)*cfg.DecodeMsPerToken*0.20

		ttft := pQueueWait + prefillMs + transferMs + math.Min(dQueueWait, cfg.DecodeMsPerToken)
		effITL := cfg.DecodeMsPerToken + math.Min(5.0, dQueueWait*0.03)

		ttfts = append(ttfts, ttft)
		itls = append(itls, effITL)
	}

	all := append(prefillPool, decodePool...)
	return buildResult(PolicyPDDisaggregated, len(trace), hits, ttfts, itls, all)
}

func pickLeastLoaded(replicas []*replica, nowMs float64) int {
	best := 0
	bestWait := math.Max(0.0, replicas[0].freeAtMs-nowMs)
	for i := 1; i < len(replicas); i++ {
		w := math.Max(0.0, replicas[i].freeAtMs-nowMs)
		if w < bestWait {
			bestWait = w
			best = i
		}
	}
	return best
}

func pickPrefixAware(replicas []*replica, req Request, maxSkewMs float64) int {
	leastIdx := pickLeastLoaded(replicas, req.ArrivalMs)
	leastWait := math.Max(0.0, replicas[leastIdx].freeAtMs-req.ArrivalMs)
	if req.PrefixKey == "" {
		return leastIdx
	}

	bestHit := -1
	bestHitWait := math.Inf(1)
	for i, r := range replicas {
		if _, ok := r.cache.entries[req.PrefixKey]; ok {
			w := math.Max(0.0, r.freeAtMs-req.ArrivalMs)
			if w < bestHitWait {
				bestHitWait = w
				bestHit = i
			}
		}
	}
	if bestHit >= 0 && (bestHitWait-leastWait) <= maxSkewMs {
		return bestHit
	}
	return leastIdx
}

func buildResult(
	policy Policy,
	n, hits int,
	ttfts, itls []float64,
	replicas []*replica,
) SimResult {
	mean := func(xs []float64) float64 {
		sum := 0.0
		for _, v := range xs {
			sum += v
		}
		return sum / float64(max(1, len(xs)))
	}
	p99 := func(xs []float64) float64 {
		cp := append([]float64(nil), xs...)
		sort.Float64s(cp)
		idx := min(len(cp)-1, int(0.99*float64(len(cp)-1)))
		return cp[idx]
	}

	maxServed := 0
	totalServed := 0
	for _, r := range replicas {
		if r.served > maxServed {
			maxServed = r.served
		}
		totalServed += r.served
	}
	meanServed := float64(totalServed) / float64(max(1, len(replicas)))
	skew := 1.0
	if meanServed > 0 {
		skew = float64(maxServed) / meanServed
	}

	return SimResult{
		Policy:          policy,
		NumRequests:     n,
		PrefixHitRate:   float64(hits) / float64(n),
		MeanTTFTMs:      mean(ttfts),
		P99TTFTMs:       p99(ttfts),
		MeanDecodeITLMs: mean(itls),
		P99DecodeITLMs:  p99(itls),
		LoadSkewRatio:   skew,
	}
}
