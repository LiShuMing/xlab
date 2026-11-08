#include "maps/operator_maps.h"

#include <iostream>
#include <limits>
#include <map>
#include <random>

namespace op = hashmap_lab::operators;
namespace {
void Require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
std::vector<op::Row> Rows(std::size_t count, bool sparse) {
    std::vector<op::Row> rows;
    std::mt19937_64 rng(73);
    for (std::size_t i = 0; i < count; ++i) {
        auto index = rng() % (i < count / 4 ? 8 : 257);
        op::Row row;
        row.key = sparse ? hashmap_lab::Mix(index) : index;
        row.value = rng() % 100;
        row.is_null = rng() % 10 == 0;
        op::Encode(row);
        rows.push_back(row);
    }
    return rows;
}
template <typename Map>
void Aggregation(bool sparse) {
    const auto rows = Rows(20000, sparse);
    Map map(0, 1024);
    std::map<std::pair<bool, std::uint64_t>, op::State> reference;
    for (std::size_t i = 0; i < rows.size(); ++i) {
        const auto& row = rows[i];
        auto& state = reference[{row.is_null, row.is_null ? 0 : row.key}];
        state.Add(row.value);
        auto actual = row.is_null ? map.AddNull(row.value)
                                  : map.Add(op::RowKey<typename Map::KeyType>(row), row.value);
        Require(actual == state, "incremental count/sum mismatch");
        if (i % 1024 == 0 || i + 1 == rows.size()) {
            std::vector<op::Group> groups;
            for (auto [key, value] : reference) groups.push_back({key.first, key.second, value});
            Require(map.Snapshot() == groups, "full aggregate snapshot mismatch");
        }
    }
    Require(map.Bytes() >= sizeof(map), "aggregate storage undercount");
}
template <typename Table>
void Join(const std::vector<op::Row>& build, const std::vector<op::Row>& probes,
          std::uint64_t minimum = 0, std::size_t domain = 1024) {
    Table table(build, minimum, domain);
    for (const auto& probe : probes) {
        op::State reference;
        for (std::size_t i = 0; i < build.size(); ++i) {
            if (!probe.is_null && !build[i].is_null && probe.key == build[i].key) {
                ++reference.count;
                reference.sum += i + 1;
            }
        }
        Require(table.Probe(probe) == reference, "join missing/duplicate/NULL result differs");
        op::JoinStats stats;
        Require(table.template Probe<true>(probe, &stats) == reference,
                "diagnostic altered semantics");
    }
}
void JoinAndMembership() {
    auto build = Rows(2048, false);
    auto probe = Rows(1000, false);
    probe.push_back({1024, 0, false, {}});
    probe.push_back({0, 0, true, {}});
    Join<op::JoinTable<op::JoinKind::kBucket>>(build, probe);
    Join<op::JoinTable<op::JoinKind::kLinear>>(build, probe);
    Join<op::JoinTable<op::JoinKind::kFingerprint>>(build, probe);
    Join<op::JoinTable<op::JoinKind::kDirect>>(build, probe);
    op::BitmapSet bitmap(0, 1024);
    op::StdSet reference(0, 1024);
    for (const auto& row : build) {
        bitmap.Insert(row);
        reference.Insert(row);
    }
    for (const auto& row : probe)
        Require(bitmap.Contains(row) == reference.Contains(row), "bitmap membership");
    std::vector<op::Row> nulls(20, {0, 0, true, {}});
    Join<op::JoinTable<op::JoinKind::kFingerprint>>(nulls, probe);
    Join<op::JoinTable<op::JoinKind::kBucket>>(nulls, probe);
    Join<op::JoinTable<op::JoinKind::kDirect>>(nulls, probe);
    Join<op::JoinTable<op::JoinKind::kFingerprint>>({}, probe);
}
void CollisionsAndBounds() {
    std::vector<op::Row> build;
    // Force both the starting bucket and fingerprint to collide; full equality is still required.
    for (std::uint64_t key = 0; build.size() < 6; ++key) {
        auto hash = hashmap_lab::Hash<std::uint64_t> {}(key);
        if ((hash & 7) == 7 && (hash >> 56) == 3) build.push_back({key, 0, false, {}});
    }
    auto probes = build;
    probes.push_back({999999, 0, false, {}});
    Join<op::JoinTable<op::JoinKind::kFingerprint>>(build, probes);
    Join<op::JoinTable<op::JoinKind::kLinear>>(build, probes);
    Join<op::JoinTable<op::JoinKind::kBucket>>(build, probes);
    auto maximum = std::numeric_limits<std::uint64_t>::max();
    std::vector<op::Row> extremes {{maximum, 0, false, {}}, {maximum - 3, 0, false, {}}};
    auto outside = extremes;
    outside.push_back({0, 0, false, {}});
    Join<op::JoinTable<op::JoinKind::kDirect>>(extremes, outside, maximum - 3, 4);
    op::BitmapSet bits(maximum - 3, 4);
    for (auto row : extremes) bits.Insert(row);
    Require(bits.Contains(extremes[0]) && !bits.Contains(outside.back()),
            "unsigned range overflow");
    bool rejected = false;
    try {
        op::DirectAggregate bad(0, 1048577);
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    Require(rejected, "unbounded direct allocation accepted");
    op::DirectAggregate direct(17, 256);
    rejected = false;
    try {
        direct.Add(16, 1);
    } catch (const std::out_of_range&) {
        rejected = true;
    }
    Require(rejected, "out-of-range direct insertion accepted");
}
} // namespace
int main() {
    try {
        Aggregation<op::StdAggregate<std::uint64_t>>(false);
        Aggregation<op::FlatAggregate<std::uint64_t, false>>(false);
        Aggregation<op::FlatAggregate<std::uint64_t, true>>(false);
        Aggregation<op::FlatAggregate<std::string_view, true>>(false);
        Aggregation<op::DirectAggregate>(false);
        Aggregation<op::StdAggregate<std::uint64_t>>(true);
        Aggregation<op::FlatAggregate<std::uint64_t, true>>(true);
        Aggregation<op::FlatAggregate<std::string_view, true>>(true);
        JoinAndMembership();
        CollisionsAndBounds();
        std::cout << "PASS: 160000 aggregate updates/full states; duplicate join rows; NULL "
                     "equality; "
                     "fingerprint collision/wraparound; bitmap; unsigned boundaries\n";
    } catch (const std::exception& e) {
        std::cerr << e.what() << '\n';
        return 1;
    }
}
