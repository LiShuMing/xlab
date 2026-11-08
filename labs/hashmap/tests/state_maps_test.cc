#include "maps/state_maps.h"

#include <iostream>
#include <limits>
#include <map>
#include <random>

namespace st = hashmap_lab::states;
namespace {
void Require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
template <std::size_t Bytes, typename Map>
void Check(bool eager, bool inline_state) {
    st::Memory memory;
    {
        Map map(&memory);
        Require(map.Find({0, false}) == nullptr, "empty lookup");
        std::map<st::Key, st::State<Bytes>> expected;
        std::mt19937_64 rng(1729);
        for (std::size_t i = 0; i < 8192; ++i) {
            st::Row row {{hashmap_lab::Mix(rng() % (i < 1024 ? 8 : 1024)), i % 17 == 0}, rng()};
            // NULL values must all share one group even with different key bits.
            if (i == 8191) row.key = {std::numeric_limits<std::uint64_t>::max(), false};
            auto& words = expected[row.key].words;
            ++words[0];
            words[1] += row.value;
            std::uint64_t bin = 0;
            if constexpr (Bytes > 16) {
                auto index = 2 + row.value % (words.size() - 2);
                words[index] += row.value;
                bin = words[index];
            }
            Require(map.Add(row) == words[0] + words[1] + bin, "stream checksum");
            if (i % 1024 == 0 || i == 8191) {
                Require(map.Size() == expected.size(), "unexpected group count");
                for (const auto& [key, value] : expected) {
                    const auto* actual = map.Find(key);
                    Require(actual && *actual == value, "state lost on rehash");
                }
            }
        }
        auto work = map.GetWork();
        Require(memory.peak >= memory.live && memory.live > 0, "memory accounting");
        Require(work.initialized_bytes == work.initializations * Bytes,
                "initialization accounting");
        if (inline_state) {
            Require(work.initializations > map.Capacity(), "empty slots not initialized");
            Require(work.relocated_bytes > 0, "rehash did not report state movement");
        } else {
            Require(work.initializations == (eager ? 8192 : map.Size()),
                    "lazy initialization count");
        }
        Require(work.rehashes > 0, "growth not exercised");
    }
    Require(memory.live == 0, "allocator did not return to zero");
}
void ArenaStabilityAndCollisions() {
    st::Memory memory;
    st::ArenaAggregate<4096, true> map(&memory);
    map.Add({{0, false}, 42});
    auto* first = map.Find({0, false});
    for (std::size_t i = 1; i < 2048; ++i) map.Add({{i, false}, i});
    Require(first == map.Find({0, false}) && first->words[1] == 42, "unstable state storage");
    Require(map.GetWork().relocated_bytes == 0, "arena moved state on rehash");
    st::InlineAggregate<16, true> collision(&memory);
    std::vector<st::Key> keys;
    for (std::uint64_t value = 0; keys.size() < 6; ++value)
        if ((st::KeyHash {}({value, false}) & 7) == 7) keys.push_back({value, false});
    for (auto key : keys) collision.Add({key, key.value});
    for (auto key : keys) Require(collision.Find(key)->words[1] == key.value, "probe wraparound");
    Require(collision.Find({99999999, false}) == nullptr, "false positive");
}
template <std::size_t Bytes>
void AllLayouts() {
    static_assert(sizeof(st::State<Bytes>) == Bytes);
    Check<Bytes, st::StdAggregate<Bytes, false, true>>(false, false);
    Check<Bytes, st::StdAggregate<Bytes, true, true>>(true, false);
    Check<Bytes, st::InlineAggregate<Bytes, true>>(false, true);
    Check<Bytes, st::ArenaAggregate<Bytes, true>>(false, false);
}
} // namespace
int main() {
    try {
        AllLayouts<16>();
        AllLayouts<256>();
        AllLayouts<4096>();
        ArenaStabilityAndCollisions();
        std::cout << "PASS: 98304 updates; all histogram words; rehash; NULL; zero/max keys; "
                     "stable arena states; collision wraparound; allocation/initialization "
                     "counters\n";
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
