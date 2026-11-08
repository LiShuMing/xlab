#ifndef HASHMAP_LAB_MAPS_OPERATOR_MAPS_H_
#define HASHMAP_LAB_MAPS_OPERATOR_MAPS_H_

#include <array>
#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <string_view>
#include <tuple>
#include <unordered_set>
#include <vector>

#include "maps/maps.h"

namespace hashmap_lab::operators {
struct State {
    std::uint64_t count = 0;
    std::uint64_t sum = 0;
    State& Add(std::uint64_t value) {
        ++count;
        sum += value;
        return *this;
    }
    bool operator==(const State&) const = default;
};
struct Group {
    bool is_null;
    std::uint64_t key;
    State state;
    bool operator==(const Group&) const = default;
    bool operator<(const Group& other) const {
        return std::tie(is_null, key) < std::tie(other.is_null, other.key);
    }
};
struct Row {
    std::uint64_t key = 0;
    std::uint64_t value = 0;
    bool is_null = false;
    std::array<char, 8> bytes {};
};
inline void Encode(Row& row) {
    for (int i = 0; i < 8; ++i) row.bytes[i] = static_cast<char>(row.key >> (i * 8));
}
template <typename Key>
Key RowKey(const Row& row) {
    if constexpr (std::is_same_v<Key, std::string_view>)
        return {row.bytes.data(), row.bytes.size()};
    else
        return row.key;
}
template <typename Key>
std::uint64_t Decode(Key key) {
    if constexpr (std::is_same_v<Key, std::string_view>) {
        std::uint64_t result = 0;
        for (std::size_t i = 0; i < key.size(); ++i)
            result |= std::uint64_t(static_cast<unsigned char>(key[i])) << (8 * i);
        return result;
    } else
        return key;
}
class NullableAggregate {
public:
    State& AddNull(std::uint64_t value) { return null_.Add(value); }

protected:
    void AppendNull(std::vector<Group>& groups) const {
        if (null_.count) groups.push_back({true, 0, null_});
    }
    State null_;
};

template <typename Key>
class StdAggregate : public NullableAggregate {
public:
    using KeyType = Key;
    StdAggregate(std::uint64_t, std::size_t)
            : map_(0, Hash<Key> {}, std::equal_to<Key> {}, Allocator(&allocation_)) {
        map_.max_load_factor(0.75);
    }
    State& Add(Key key, std::uint64_t value) { return map_[key].Add(value); }
    std::vector<Group> Snapshot() const {
        std::vector<Group> groups;
        for (const auto& [key, state] : map_) groups.push_back({false, Decode(key), state});
        AppendNull(groups);
        std::sort(groups.begin(), groups.end());
        return groups;
    }
    std::size_t Bytes() const { return sizeof(*this) + allocation_.live; }
    std::size_t Capacity() const { return map_.bucket_count(); }

private:
    using Allocator = CountingAllocator<std::pair<const Key, State>>;
    Allocation allocation_;
    std::unordered_map<Key, State, Hash<Key>, std::equal_to<Key>, Allocator> map_;
};

// Append-only GROUP BY table: count==0 denotes an empty slot; no deletion metadata.
template <typename Key, bool Fingerprint>
class FlatAggregate : public NullableAggregate {
public:
    using KeyType = Key;
    FlatAggregate(std::uint64_t, std::size_t) : slots_(8) {}
    State& Add(Key key, std::uint64_t value) {
        auto index = Locate(key);
        if (!slots_[index].state.count && (size_ + 1) * 4 > slots_.size() * 3) {
            Grow();
            index = Locate(key);
        }
        auto& slot = slots_[index];
        if (!slot.state.count) {
            slot.key = key;
            slot.fp = Hash<Key> {}(key) >> 56;
            ++size_;
        }
        return slot.state.Add(value);
    }
    std::vector<Group> Snapshot() const {
        std::vector<Group> groups;
        for (const auto& slot : slots_) {
            if (slot.state.count) groups.push_back({false, Decode(slot.key), slot.state});
        }
        AppendNull(groups);
        std::sort(groups.begin(), groups.end());
        return groups;
    }
    std::size_t Bytes() const { return sizeof(*this) + slots_.capacity() * sizeof(Slot); }
    std::size_t Capacity() const { return slots_.size(); }

private:
    struct Slot {
        Key key {};
        State state;
        std::uint8_t fp = 0;
    };
    std::size_t Locate(Key key) const {
        auto hash = Hash<Key> {}(key);
        std::size_t index = hash & (slots_.size() - 1);
        auto fp = static_cast<std::uint8_t>(hash >> 56);
        while (slots_[index].state.count) {
            if ((!Fingerprint || slots_[index].fp == fp) && slots_[index].key == key) break;
            index = (index + 1) & (slots_.size() - 1);
        }
        return index;
    }
    void Grow() {
        auto old = std::move(slots_);
        slots_ = std::vector<Slot>(old.size() * 2);
        for (const auto& slot : old) {
            if (slot.state.count) slots_[Locate(slot.key)] = slot;
        }
    }
    std::vector<Slot> slots_;
    std::size_t size_ = 0;
};

class DirectAggregate : public NullableAggregate {
public:
    using KeyType = std::uint64_t;
    DirectAggregate(std::uint64_t minimum, std::size_t domain)
            : minimum_(minimum), states_(CheckedDomain(domain)) {}
    State& Add(std::uint64_t key, std::uint64_t value) {
        if (key < minimum_ || key - minimum_ >= states_.size())
            throw std::out_of_range("direct aggregate key");
        return states_[key - minimum_].Add(value);
    }
    std::vector<Group> Snapshot() const {
        std::vector<Group> groups;
        for (std::size_t i = 0; i < states_.size(); ++i) {
            if (states_[i].count) groups.push_back({false, minimum_ + i, states_[i]});
        }
        AppendNull(groups);
        std::sort(groups.begin(), groups.end());
        return groups;
    }
    std::size_t Bytes() const { return sizeof(*this) + states_.capacity() * sizeof(State); }
    std::size_t Capacity() const { return states_.size(); }
    static std::size_t CheckedDomain(std::size_t domain) {
        if (!domain || domain > (1U << 20))
            throw std::invalid_argument("direct domain exceeds 1M cells");
        return domain;
    }

private:
    std::uint64_t minimum_;
    std::vector<State> states_;
};

enum class JoinKind { kBucket, kLinear, kFingerprint, kDirect };
struct JoinStats {
    std::uint64_t steps = 0, comparisons = 0;
};

template <JoinKind Kind>
class JoinTable {
public:
    JoinTable(const std::vector<Row>& build, std::uint64_t minimum, std::size_t domain)
            : build_(build), minimum_(minimum), next_(build.size() + 1, 0) {
        // The fingerprint variant uses 8 bits of fingerprint and a 24-bit row id.
        if (build.size() >= (1U << 24)) throw std::invalid_argument("join row id exceeds 24 bits");
        std::size_t capacity = 8;
        if constexpr (Kind == JoinKind::kDirect)
            capacity = DirectAggregate::CheckedDomain(domain);
        else
            while (capacity * 0.75 < build.size()) capacity *= 2;
        first_.resize(capacity, 0);
        for (std::size_t i = 0; i < build.size(); ++i) {
            if (build[i].is_null) continue; // SQL equality: NULL never matches NULL.
            auto index = BuildSlot(build[i].key);
            next_[i + 1] = Head(first_[index]);
            first_[index] = EncodeHead(i + 1, Hash<std::uint64_t> {}(build[i].key));
        }
    }
    template <bool Track = false>
    State Probe(const Row& row, JoinStats* stats = nullptr) const {
        State result;
        if (row.is_null) return result;
        auto hash = Hash<std::uint64_t> {}(row.key);
        std::size_t index;
        if constexpr (Kind == JoinKind::kDirect) {
            if (row.key < minimum_ || row.key - minimum_ >= first_.size()) return result;
            index = row.key - minimum_;
            if constexpr (Track) ++stats->steps;
        } else {
            index = hash & (first_.size() - 1);
            if constexpr (Kind == JoinKind::kBucket) {
                if constexpr (Track) ++stats->steps;
            } else {
                while (true) {
                    if constexpr (Track) ++stats->steps;
                    auto entry = first_[index];
                    if (!Head(entry)) return result;
                    bool candidate =
                            Kind != JoinKind::kFingerprint || (entry >> 24) == (hash >> 56);
                    if (candidate) {
                        if constexpr (Track) ++stats->comparisons;
                        if (build_[Head(entry) - 1].key == row.key) break;
                    }
                    index = (index + 1) & (first_.size() - 1);
                }
            }
        }
        for (auto id = Head(first_[index]); id; id = next_[id]) {
            if constexpr (Track) ++stats->steps;
            bool match = true;
            if constexpr (Kind == JoinKind::kBucket) {
                if constexpr (Track) ++stats->comparisons;
                match = build_[id - 1].key == row.key;
            }
            if (match) {
                ++result.count;
                result.sum += id;
            }
        }
        return result;
    }
    std::size_t Bytes() const {
        return sizeof(*this) + (first_.capacity() + next_.capacity()) * sizeof(std::uint32_t);
    }
    std::size_t Capacity() const { return first_.size(); }

private:
    static std::uint32_t Head(std::uint32_t entry) {
        if constexpr (Kind == JoinKind::kFingerprint)
            return entry & 0xFFFFFF;
        else
            return entry;
    }
    static std::uint32_t EncodeHead(std::uint32_t id, std::uint64_t hash) {
        if constexpr (Kind == JoinKind::kFingerprint)
            return (static_cast<std::uint32_t>(hash >> 56) << 24) | id;
        else
            return id;
    }
    std::size_t BuildSlot(std::uint64_t key) const {
        if constexpr (Kind == JoinKind::kDirect) {
            if (key < minimum_ || key - minimum_ >= first_.size())
                throw std::out_of_range("direct join key");
            return key - minimum_;
        } else {
            auto hash = Hash<std::uint64_t> {}(key);
            auto index = hash & (first_.size() - 1);
            if constexpr (Kind != JoinKind::kBucket) {
                while (Head(first_[index])) {
                    if ((Kind != JoinKind::kFingerprint || (first_[index] >> 24) == (hash >> 56)) &&
                        build_[Head(first_[index]) - 1].key == key)
                        break;
                    index = (index + 1) & (first_.size() - 1);
                }
            }
            return index;
        }
    }
    const std::vector<Row>& build_;
    std::uint64_t minimum_;
    std::vector<std::uint32_t> first_, next_;
};

class BitmapSet {
public:
    BitmapSet(std::uint64_t minimum, std::size_t domain)
            : minimum_(minimum),
              domain_(DirectAggregate::CheckedDomain(domain)),
              bits_((domain + 63) / 64, 0) {}
    void Insert(const Row& row) {
        if (row.is_null) return;
        if (row.key < minimum_ || row.key - minimum_ >= domain_)
            throw std::out_of_range("bitmap key");
        auto offset = row.key - minimum_;
        bits_[offset / 64] |= std::uint64_t {1} << (offset % 64);
    }
    bool Contains(const Row& row) const {
        if (row.is_null || row.key < minimum_ || row.key - minimum_ >= domain_) return false;
        auto offset = row.key - minimum_;
        return (bits_[offset / 64] >> (offset % 64)) & 1;
    }
    std::size_t Bytes() const { return sizeof(*this) + bits_.capacity() * sizeof(std::uint64_t); }
    std::size_t Capacity() const { return domain_; }

private:
    std::uint64_t minimum_;
    std::size_t domain_;
    std::vector<std::uint64_t> bits_;
};
class StdSet {
public:
    StdSet(std::uint64_t, std::size_t)
            : set_(0, Hash<std::uint64_t> {}, std::equal_to<std::uint64_t> {},
                   Allocator(&allocation_)) {}
    void Insert(const Row& row) {
        if (!row.is_null) set_.insert(row.key);
    }
    bool Contains(const Row& row) const { return !row.is_null && set_.contains(row.key); }
    std::size_t Bytes() const { return sizeof(*this) + allocation_.live; }
    std::size_t Capacity() const { return set_.bucket_count(); }

private:
    using Allocator = CountingAllocator<std::uint64_t>;
    Allocation allocation_;
    std::unordered_set<std::uint64_t, Hash<std::uint64_t>, std::equal_to<std::uint64_t>, Allocator>
            set_;
};
} // namespace hashmap_lab::operators
#endif // HASHMAP_LAB_MAPS_OPERATOR_MAPS_H_
