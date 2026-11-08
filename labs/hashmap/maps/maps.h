#ifndef HASHMAP_LAB_MAPS_MAPS_H_
#define HASHMAP_LAB_MAPS_MAPS_H_

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string_view>
#include <type_traits>
#include <unordered_map>
#include <utility>
#include <vector>

namespace hashmap_lab {

inline std::uint64_t Mix(std::uint64_t value) {
    value = (value ^ (value >> 30)) * 0xbf58476d1ce4e5b9ULL;
    value = (value ^ (value >> 27)) * 0x94d049bb133111ebULL;
    return value ^ (value >> 31);
}

template <typename Key>
struct Hash {
    std::size_t operator()(Key key) const {
        if constexpr (std::is_same_v<Key, std::string_view>) {
            std::uint64_t hash = 14695981039346656037ULL;
            for (unsigned char byte : key) hash = (hash ^ byte) * 1099511628211ULL;
            return Mix(hash);
        } else {
            return Mix(key);
        }
    }
};

struct Allocation {
    std::size_t live = 0;
};

template <typename T>
struct CountingAllocator {
    using value_type = T;
    Allocation* allocation;
    explicit CountingAllocator(Allocation* value) : allocation(value) {}
    template <typename U>
    CountingAllocator(const CountingAllocator<U>& other) : allocation(other.allocation) {}
    T* allocate(std::size_t count) {
        T* result = std::allocator<T> {}.allocate(count);
        allocation->live += count * sizeof(T);
        return result;
    }
    void deallocate(T* ptr, std::size_t count) {
        allocation->live -= count * sizeof(T);
        std::allocator<T> {}.deallocate(ptr, count);
    }
    template <typename U>
    bool operator==(const CountingAllocator<U>& other) const {
        return allocation == other.allocation;
    }
};

template <typename Key>
class StdMap {
public:
    explicit StdMap(std::size_t expected = 0, double load = 0.75)
            : map_(0, Hash<Key> {}, std::equal_to<Key> {}, Allocator(&allocation_)) {
        map_.max_load_factor(load);
        if (expected) map_.reserve(expected);
    }
    bool Insert(Key key, std::uint32_t value) { return map_.insert_or_assign(key, value).second; }
    bool Erase(Key key) { return map_.erase(key) != 0; }
    std::optional<std::uint32_t> Find(Key key) const {
        auto found = map_.find(key);
        if (found == map_.end()) return std::nullopt;
        return found->second;
    }
    std::size_t Size() const { return map_.size(); }
    std::size_t Capacity() const { return map_.bucket_count(); }
    std::size_t Bytes() const { return sizeof(*this) + allocation_.live; }
    StdMap(const StdMap&) = delete;
    StdMap& operator=(const StdMap&) = delete;

private:
    using Allocator = CountingAllocator<std::pair<const Key, std::uint32_t>>;
    Allocation allocation_;
    std::unordered_map<Key, std::uint32_t, Hash<Key>, std::equal_to<Key>, Allocator> map_;
};

struct ProbeStats {
    std::size_t probes = 0;
    std::size_t comparisons = 0;
};

// Linear probing with tombstones. Keys are non-owning; the caller owns stable storage.
template <typename Key>
class LinearMap {
public:
    explicit LinearMap(std::size_t expected = 0, double load = 0.75) : max_load_(load) {
        if (!(load > 0 && load < 1)) throw std::invalid_argument("load must be in (0, 1)");
        std::size_t capacity = 8;
        while (capacity * load < expected) capacity *= 2;
        slots_.resize(capacity);
    }
    bool Insert(Key key, std::uint32_t value) {
        auto [position, found] = Locate(key);
        if (found) {
            slots_[position].value = value;
            return false;
        }
        if (occupied_ + 1 > slots_.size() * max_load_) {
            Rehash((size_ + 1 <= slots_.size() * max_load_) ? slots_.size() : slots_.size() * 2);
            position = Locate(key).first;
        }
        if (slots_[position].state == State::kEmpty) ++occupied_;
        slots_[position] = {key, value, State::kLive};
        ++size_;
        return true;
    }
    bool Erase(Key key) {
        const auto [position, found] = Locate(key);
        if (!found) return false;
        slots_[position].state = State::kDeleted;
        --size_;
        return true;
    }
    std::optional<std::uint32_t> Find(Key key) const {
        const std::size_t mask = slots_.size() - 1;
        std::size_t index = Hash<Key> {}(key)&mask;
        for (std::size_t steps = 0; steps < slots_.size(); ++steps) {
            const auto& slot = slots_[index];
            if (slot.state == State::kEmpty) return std::nullopt;
            if (slot.state == State::kLive && slot.key == key) return slot.value;
            index = (index + 1) & mask;
        }
        return std::nullopt;
    }
    ProbeStats Diagnose(Key key) const {
        ProbeStats stats;
        const std::size_t mask = slots_.size() - 1;
        std::size_t index = Hash<Key> {}(key)&mask;
        for (std::size_t steps = 0; steps < slots_.size(); ++steps) {
            const auto& slot = slots_[index];
            ++stats.probes;
            if (slot.state == State::kEmpty) break;
            if (slot.state == State::kLive) {
                ++stats.comparisons;
                if (slot.key == key) break;
            }
            index = (index + 1) & mask;
        }
        return stats;
    }
    std::size_t Size() const { return size_; }
    std::size_t Capacity() const { return slots_.size(); }
    std::size_t Bytes() const { return sizeof(*this) + slots_.capacity() * sizeof(Slot); }

private:
    enum class State : std::uint8_t { kEmpty, kLive, kDeleted };
    struct Slot {
        Key key {};
        std::uint32_t value = 0;
        State state = State::kEmpty;
    };
    std::pair<std::size_t, bool> Locate(Key key) const {
        const std::size_t mask = slots_.size() - 1;
        std::size_t index = Hash<Key> {}(key)&mask;
        std::size_t deleted = slots_.size();
        for (std::size_t steps = 0; steps < slots_.size(); ++steps) {
            const auto& slot = slots_[index];
            if (slot.state == State::kEmpty) {
                return {deleted == slots_.size() ? index : deleted, false};
            }
            if (slot.state == State::kLive && slot.key == key) return {index, true};
            if (slot.state == State::kDeleted && deleted == slots_.size()) deleted = index;
            index = (index + 1) & mask;
        }
        if (deleted != slots_.size()) return {deleted, false};
        throw std::logic_error("linear probing invariant: no free slot");
    }
    void Rehash(std::size_t capacity) {
        auto old = std::move(slots_);
        slots_ = std::vector<Slot>(capacity);
        size_ = 0;
        occupied_ = 0;
        for (const auto& slot : old) {
            if (slot.state == State::kLive) Insert(slot.key, slot.value);
        }
    }
    std::vector<Slot> slots_;
    std::size_t size_ = 0;
    std::size_t occupied_ = 0;
    double max_load_;
};

template <typename Key>
class SortedMap {
public:
    explicit SortedMap(const std::vector<Key>& keys) {
        for (std::size_t i = 0; i < keys.size(); ++i) entries_.emplace_back(keys[i], i + 1);
        std::sort(entries_.begin(), entries_.end());
    }
    std::optional<std::uint32_t> Find(Key key) const {
        auto found =
                std::lower_bound(entries_.begin(), entries_.end(), key,
                                 [](const auto& entry, Key query) { return entry.first < query; });
        if (found == entries_.end() || found->first != key) return std::nullopt;
        return found->second;
    }
    std::size_t Size() const { return entries_.size(); }
    std::size_t Capacity() const { return entries_.capacity(); }
    std::size_t Bytes() const { return sizeof(*this) + entries_.capacity() * sizeof(entries_[0]); }

private:
    std::vector<std::pair<Key, std::uint32_t>> entries_;
};

} // namespace hashmap_lab
#endif // HASHMAP_LAB_MAPS_MAPS_H_
