#include <iostream>
#include <random>
#include <unordered_map>

#include "bench/bench.h"

namespace {
void Require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error(message);
}

template <typename Map>
void Differential(double load) {
    Map map(0, load);
    std::unordered_map<std::uint64_t, std::uint32_t> reference;
    std::mt19937_64 rng(20261108);
    for (int step = 0; step < 100000; ++step) {
        const auto key = rng() % 1024;
        auto value = static_cast<std::uint32_t>(rng());
        switch (rng() % 3) {
        case 0:
            Require(map.Insert(key, value) == reference.insert_or_assign(key, value).second,
                    "insert differs");
            break;
        case 1:
            Require(map.Erase(key) == (reference.erase(key) != 0), "erase differs");
            break;
        default:
            auto found = reference.find(key);
            auto expected = found == reference.end() ? std::nullopt : std::optional(found->second);
            Require(map.Find(key) == expected, "lookup differs");
        }
        Require(map.Size() == reference.size(), "size differs");
    }
    for (auto [key, value] : reference)
        Require(map.Find(key) == std::optional(value), "final contents differ");
    for (std::uint64_t key = 0; key < 1024; ++key) map.Erase(key);
    Require(map.Size() == 0, "clear by erase failed");
    Require(!map.Find(0), "deleted zero key returned");
    Require(map.Insert(0, 0), "zero key/value insertion failed");
    Require(map.Find(0) == std::optional<std::uint32_t>(0), "zero value confused with missing");
}

void CollisionAndWraparound() {
    hashmap_lab::LinearMap<std::uint64_t> map(0, 0.9);
    std::vector<std::uint64_t> keys;
    for (std::uint64_t key = 0; keys.size() < 6; ++key) {
        if ((hashmap_lab::Hash<std::uint64_t> {}(key) & 7) == 7) keys.push_back(key);
    }
    for (std::size_t i = 0; i < keys.size(); ++i) map.Insert(keys[i], i);
    Require(map.Diagnose(keys.back()).probes == 6, "collision fixture did not wrap");
    map.Erase(keys[0]);
    map.Erase(keys[2]);
    Require(map.Find(keys.back()) == std::optional<std::uint32_t>(5), "tombstone broke chain");
    Require(!map.Insert(keys.back(), 99), "update after tombstone duplicated key");
    Require(map.Size() == 4, "duplicate after tombstone");
    for (int i = 0; i < 500; ++i) {
        for (std::size_t j = 0; j < keys.size(); ++j) map.Insert(keys[j], j);
        for (auto key : keys) Require(map.Erase(key), "tombstone reuse failed");
    }
}

void StringAndTrace() {
    using namespace hashmap_lab;
    std::string empty, embedded("a\0b", 3), prefix("a\0c", 3), long_key(200, 'x');
    LinearMap<std::string_view> map;
    map.Insert(empty, 1);
    map.Insert(embedded, 2);
    map.Insert(long_key, 3);
    Require(map.Find(std::string("a\0b", 3)) == std::optional<std::uint32_t>(2), "embedded NUL");
    Require(!map.Find(prefix), "embedded NUL false positive");
    Require(map.Find(empty) == std::optional<std::uint32_t>(1), "empty key");
    Options options;
    options.hit = 50;
    options.distribution = "hot";
    auto data = MakeDataset<std::string_view>(options, {"a", "bb", "ccc", "dddd"});
    LinearMap<std::string_view> fresh;
    Populate(fresh, data);
    Verify(fresh, data);
    for (std::size_t i = 0; i < data.queries.size(); ++i) {
        if (data.expected[i])
            Require(data.queries[i].data() != data.keys[data.expected[i] - 1].data(),
                    "query aliases build key");
    }
    auto again = MakeDataset<std::string_view>(options, {"a", "bb", "ccc", "dddd"});
    Require(data.trace_hash == again.trace_hash, "non-deterministic trace");
    options.seed++;
    auto different = MakeDataset<std::string_view>(options, {"a", "bb", "ccc", "dddd"});
    Require(data.trace_hash != different.trace_hash, "seed ignored");
    Require(std::count_if(data.expected.begin(), data.expected.end(),
                          [](auto v) { return v != 0; }) == 8192,
            "hit ratio not exact");
    Require(ChurnBatch(fresh, data) == 16384, "churn checksum");
    Verify(fresh, data);
}
} // namespace

int main() {
    try {
        for (double load : {0.5, 0.75, 0.85, 0.9}) {
            Differential<hashmap_lab::LinearMap<std::uint64_t>>(load);
            Differential<hashmap_lab::StdMap<std::uint64_t>>(load);
        }
        CollisionAndWraparound();
        StringAndTrace();
        std::cout << "PASS: 800000 differential operations; collision/wraparound/tombstones; "
                     "empty/NUL/zero; independent query storage; trace; churn\n";
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
