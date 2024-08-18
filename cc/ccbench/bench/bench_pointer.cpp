#include "include/fwd.h"

#include <random>
#include <vector>
#include <algorithm>

//=============================================================================
// Sequential Pointer Chasing
// Each element points to the next one: 0 -> 1 -> 2 -> ... -> n-1 -> 0
// This represents a simple linked list traversal
//=============================================================================
static void BM_PointerChasing_Sequential(benchmark::State& state) {
    size_t n = state.range(0);
    std::vector<size_t> next(n);
    for (size_t i = 0; i < n; ++i) {
        next[i] = (i + 1) % n;  // Circular linked list
    }

    size_t idx = 0;
    for (auto _ : state) {
        idx = next[idx];
        benchmark::DoNotOptimize(idx);
    }
}
BENCHMARK(BM_PointerChasing_Sequential)->Range(1024, 1024 * 1024);

//=============================================================================
// Random Pointer Chasing
// Each element points to a random location in the array
// This tests cache miss behavior and memory latency
//=============================================================================
static void BM_PointerChasing_Random(benchmark::State& state) {
    size_t n = state.range(0);
    static std::mt19937_64 rng(42);
    std::vector<size_t> next(n);
    for (size_t i = 0; i < n; ++i) {
        next[i] = rng() % n;
    }

    size_t idx = 0;
    for (auto _ : state) {
        idx = next[idx];
        benchmark::DoNotOptimize(idx);
    }
}
BENCHMARK(BM_PointerChasing_Random)->Range(1024, 1024 * 1024);

//=============================================================================
// Strided Pointer Chasing
// Jump by a fixed stride through the array
// This tests cache behavior with predictable but not sequential access
//=============================================================================
static void BM_PointerChasing_Strided(benchmark::State& state) {
    size_t n = state.range(0);
    size_t stride = state.range(1);
    if (stride == 0) stride = 7;  // Default stride

    size_t idx = 0;
    for (auto _ : state) {
        idx = (idx + stride) % n;
        benchmark::DoNotOptimize(idx);
    }
}
BENCHMARK(BM_PointerChasing_Strided)
    ->Ranges({{1024, 1024 * 1024}, {3, 127}})
    ->Complexity();

//=============================================================================
// Backward Pointer Chasing
// Traverse the linked list in reverse order
//=============================================================================
static void BM_PointerChasing_Backward(benchmark::State& state) {
    size_t n = state.range(0);
    std::vector<size_t> prev(n);
    for (size_t i = 0; i < n; ++i) {
        prev[i] = (i == 0) ? n - 1 : i - 1;
    }

    size_t idx = 0;
    for (auto _ : state) {
        idx = prev[idx];
        benchmark::DoNotOptimize(idx);
    }
}
BENCHMARK(BM_PointerChasing_Backward)->Range(1024, 1024 * 1024);

//=============================================================================
// Bidirectional Pointer Chasing
// Alternating between forward and backward traversal
//=============================================================================
static void BM_PointerChasing_Bidirectional(benchmark::State& state) {
    size_t n = state.range(0);
    std::vector<size_t> next(n), prev(n);
    for (size_t i = 0; i < n; ++i) {
        next[i] = (i + 1) % n;
        prev[i] = (i == 0) ? n - 1 : i - 1;
    }

    size_t idx = 0;
    bool forward = true;
    for (auto _ : state) {
        idx = forward ? next[idx] : prev[idx];
        forward = !forward;
        benchmark::DoNotOptimize(idx);
    }
}
BENCHMARK(BM_PointerChasing_Bidirectional)->Range(1024, 1024 * 1024);

//=============================================================================
// Multiple Independent Pointers
// Several pointers chasing through the same structure
// Tests cache contention between pointers
//=============================================================================
static void BM_PointerChasing_Multiple(benchmark::State& state) {
    size_t n = state.range(0);
    int num_pointers = state.range(1);
    if (num_pointers == 0) num_pointers = 4;

    std::vector<size_t> next(n);
    for (size_t i = 0; i < n; ++i) {
        next[i] = (i + 1) % n;
    }

    std::vector<size_t> indices(num_pointers, 0);
    for (auto _ : state) {
        for (int i = 0; i < num_pointers; ++i) {
            indices[i] = next[indices[i]];
        }
        benchmark::DoNotOptimize(indices);
    }
}
BENCHMARK(BM_PointerChasing_Multiple)
    ->Ranges({{1024, 1024 * 1024}, {1, 16}})
    ->Iterations(10000);

//=============================================================================
// Sparse Pointer Chasing
// Only every k-th element is part of the chain
// Tests cache line utilization
//=============================================================================
static void BM_PointerChasing_Sparse(benchmark::State& state) {
    size_t n = state.range(0);
    size_t density = state.range(1);
    if (density == 0) density = 16;  // 1/density of elements are used

    std::vector<size_t> next(n, 0);
    std::vector<size_t> active_indices;
    active_indices.reserve(n / density);

    for (size_t i = 0; i < n; ++i) {
        if (i % density == 0) {
            active_indices.push_back(i);
        }
    }

    for (size_t i = 0; i < active_indices.size(); ++i) {
        next[active_indices[i]] = active_indices[(i + 1) % active_indices.size()];
    }

    size_t idx = active_indices[0];
    for (auto _ : state) {
        idx = next[idx];
        benchmark::DoNotOptimize(idx);
    }
}
BENCHMARK(BM_PointerChasing_Sparse)
    ->Ranges({{1024 * 1024, 64 * 1024 * 1024}, {4, 64}})
    ->Complexity();

//=============================================================================
// Tree Pointer Chasing
// Each node has two children, traverse breadth-first style
// Tests cache behavior with branching structures
//=============================================================================
static void BM_PointerChasing_Tree(benchmark::State& state) {
    size_t n = state.range(0);
    // Build a complete binary tree
    std::vector<size_t> left(n), right(n);
    for (size_t i = 0; i < n; ++i) {
        left[i] = (2 * i + 1 < n) ? 2 * i + 1 : i;
        right[i] = (2 * i + 2 < n) ? 2 * i + 2 : i;
    }

    size_t idx = 0;
    bool use_left = true;
    for (auto _ : state) {
        idx = use_left ? left[idx] : right[idx];
        use_left = !use_left;
        benchmark::DoNotOptimize(idx);
    }
}
BENCHMARK(BM_PointerChasing_Tree)->Range(1024, 1024 * 1024);

//=============================================================================
// Reverse Random Pointer Chasing
// Build random links, then traverse backwards
//=============================================================================
static void BM_PointerChasing_ReverseRandom(benchmark::State& state) {
    size_t n = state.range(0);
    static std::mt19937_64 rng(42);
    std::vector<size_t> next(n), prev(n);
    for (size_t i = 0; i < n; ++i) {
        next[i] = rng() % n;
    }
    // Build reverse mapping
    for (size_t i = 0; i < n; ++i) {
        prev[next[i]] = i;
    }

    size_t idx = 0;
    for (auto _ : state) {
        idx = prev[idx];
        benchmark::DoNotOptimize(idx);
    }
}
BENCHMARK(BM_PointerChasing_ReverseRandom)->Range(1024, 1024 * 1024);

//=============================================================================
// Hot/Cold Pointer Chasing
// Most pointers jump to a few "hot" nodes
// Tests cache pollution from frequently accessed nodes
//=============================================================================
static void BM_PointerChasing_HotCold(benchmark::State& state) {
    size_t n = state.range(0);
    static std::mt19937_64 rng(42);
    std::uniform_int_distribution<size_t> dist(0, n - 1);

    std::vector<size_t> next(n);
    // 20% of nodes are "hot" (point to random locations)
    // 80% of nodes are "cold" (point to hot nodes)
    size_t hot_threshold = n / 5;
    for (size_t i = 0; i < n; ++i) {
        if (i < hot_threshold) {
            next[i] = dist(rng);  // Hot nodes point randomly
        } else {
            next[i] = dist(rng) % hot_threshold;  // Cold nodes point to hot
        }
    }

    size_t idx = hot_threshold;  // Start from a cold node
    for (auto _ : state) {
        idx = next[idx];
        benchmark::DoNotOptimize(idx);
    }
}
BENCHMARK(BM_PointerChasing_HotCold)->Range(1024, 1024 * 1024);

BENCHMARK_MAIN();
