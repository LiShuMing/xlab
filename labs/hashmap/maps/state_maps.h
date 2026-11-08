#ifndef HASHMAP_LAB_MAPS_STATE_MAPS_H_
#define HASHMAP_LAB_MAPS_STATE_MAPS_H_

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <memory>
#include <stdexcept>
#include <unordered_map>
#include <utility>
#include <vector>

#include "maps/maps.h"

namespace hashmap_lab::states {
struct Key {
    std::uint64_t value = 0;
    bool is_null = false;
    bool operator==(const Key& other) const {
        return is_null == other.is_null && (is_null || value == other.value);
    }
    bool operator<(const Key& other) const {
        if (is_null != other.is_null) return is_null < other.is_null;
        return !is_null && value < other.value;
    }
};
struct KeyHash {
    std::size_t operator()(Key key) const {
        return Mix(key.is_null ? 0x9e3779b97f4a7c15ULL : key.value);
    }
};
struct Row {
    Key key;
    std::uint64_t value;
};

// Larger states are actual sum histograms, not unused padding. One bin changes per row.
template <std::size_t Bytes>
struct State {
    static_assert(Bytes >= 16 && Bytes % 8 == 0);
    std::array<std::uint64_t, Bytes / 8> words {};
    std::uint64_t Add(std::uint64_t value) {
        ++words[0];
        words[1] += value;
        std::uint64_t bin = 0;
        if constexpr (Bytes > 16) {
            auto index = 2 + value % (words.size() - 2);
            words[index] += value;
            bin = words[index];
        }
        return words[0] + words[1] + bin;
    }
    bool operator==(const State&) const = default;
};

struct Memory {
    std::size_t live = 0, peak = 0, allocations = 0, requested = 0;
};
template <typename T, bool Track>
struct Allocator {
    using value_type = T;
    template <typename U>
    struct rebind {
        using other = Allocator<U, Track>;
    };
    Memory* memory;
    explicit Allocator(Memory* value) : memory(value) {}
    template <typename U>
    Allocator(const Allocator<U, Track>& other) : memory(other.memory) {}
    T* allocate(std::size_t count) {
        T* result = std::allocator<T> {}.allocate(count);
        if constexpr (Track) {
            memory->live += count * sizeof(T);
            memory->requested += count * sizeof(T);
            memory->peak = std::max(memory->peak, memory->live);
            ++memory->allocations;
        }
        return result;
    }
    void deallocate(T* pointer, std::size_t count) {
        if constexpr (Track) memory->live -= count * sizeof(T);
        std::allocator<T> {}.deallocate(pointer, count);
    }
    template <typename U>
    bool operator==(const Allocator<U, Track>& other) const {
        return memory == other.memory;
    }
};
struct Work {
    std::size_t initializations = 0, initialized_bytes = 0, relocated_bytes = 0, rehashes = 0;
};

template <std::size_t Bytes, bool Eager, bool Track = false>
class StdAggregate {
public:
    using Value = State<Bytes>;
    explicit StdAggregate(Memory* memory)
            : map_(0, KeyHash {}, std::equal_to<Key> {}, MapAllocator(memory)) {
        map_.max_load_factor(0.75);
    }
    std::uint64_t Add(const Row& row) {
        [[maybe_unused]] auto capacity = map_.bucket_count();
        auto [position, inserted] = [&]() {
            if constexpr (Eager) {
                // Constructing a mapped argument before emplace is a common eager API pattern.
                Value candidate {};
                return map_.emplace(row.key, std::move(candidate));
            } else {
                return map_.try_emplace(row.key);
            }
        }();
        if constexpr (Track) {
            work_.initializations += Eager || inserted;
            work_.initialized_bytes += (Eager || inserted) ? Bytes : 0;
            if constexpr (Eager) work_.relocated_bytes += inserted ? Bytes : 0;
            work_.rehashes += capacity != map_.bucket_count();
        }
        return position->second.Add(row.value);
    }
    const Value* Find(Key key) const {
        auto it = map_.find(key);
        return it == map_.end() ? nullptr : &it->second;
    }
    std::size_t Size() const { return map_.size(); }
    std::size_t Capacity() const { return map_.bucket_count(); }
    Work GetWork() const { return work_; }

private:
    using MapAllocator = Allocator<std::pair<const Key, Value>, Track>;
    std::unordered_map<Key, Value, KeyHash, std::equal_to<Key>, MapAllocator> map_;
    Work work_;
};

template <std::size_t Bytes, bool Track = false>
class InlineAggregate {
public:
    using Value = State<Bytes>;
    explicit InlineAggregate(Memory* memory) : slots_(8, Allocator<Slot, Track>(memory)) {
        if constexpr (Track) {
            work_.initializations = 8;
            work_.initialized_bytes = 8 * Bytes;
        }
    }
    std::uint64_t Add(const Row& row) {
        auto index = Locate(row.key);
        if (!slots_[index].occupied && (size_ + 1) * 4 > slots_.size() * 3) {
            Grow();
            index = Locate(row.key);
        }
        auto& slot = slots_[index];
        if (!slot.occupied) {
            slot.key = row.key;
            slot.occupied = true;
            ++size_;
        }
        return slot.value.Add(row.value);
    }
    const Value* Find(Key key) const {
        const auto& slot = slots_[Locate(key)];
        return slot.occupied ? &slot.value : nullptr;
    }
    std::size_t Size() const { return size_; }
    std::size_t Capacity() const { return slots_.size(); }
    Work GetWork() const { return work_; }

private:
    struct Slot {
        Key key;
        Value value;
        bool occupied = false;
    };
    std::size_t Locate(Key key) const {
        auto index = KeyHash {}(key) & (slots_.size() - 1);
        while (slots_[index].occupied && !(slots_[index].key == key))
            index = (index + 1) & (slots_.size() - 1);
        return index;
    }
    void Grow() {
        auto old = std::move(slots_);
        slots_ = decltype(slots_)(old.size() * 2, old.get_allocator());
        for (const auto& slot : old)
            if (slot.occupied) slots_[Locate(slot.key)] = slot;
        if constexpr (Track) {
            work_.initializations += slots_.size();
            work_.initialized_bytes += slots_.size() * Bytes;
            work_.relocated_bytes += size_ * Bytes;
            ++work_.rehashes;
        }
    }
    std::vector<Slot, Allocator<Slot, Track>> slots_;
    std::size_t size_ = 0;
    Work work_;
};

template <std::size_t Bytes, bool Track = false>
class ArenaAggregate {
public:
    using Value = State<Bytes>;
    explicit ArenaAggregate(Memory* memory)
            : slots_(8, Allocator<Slot, Track>(memory)), states_(Allocator<Value, Track>(memory)) {}
    std::uint64_t Add(const Row& row) {
        auto index = Locate(row.key);
        if (!slots_[index].id && (states_.size() + 1) * 4 > slots_.size() * 3) {
            Grow();
            index = Locate(row.key);
        }
        auto& slot = slots_[index];
        if (!slot.id) {
            // deque provides stable state storage; rehash moves only key + row index.
            states_.emplace_back();
            slot.key = row.key;
            slot.id = states_.size();
            if constexpr (Track) {
                ++work_.initializations;
                work_.initialized_bytes += Bytes;
            }
        }
        return states_[slot.id - 1].Add(row.value);
    }
    const Value* Find(Key key) const {
        const auto& slot = slots_[Locate(key)];
        return slot.id ? &states_[slot.id - 1] : nullptr;
    }
    std::size_t Size() const { return states_.size(); }
    std::size_t Capacity() const { return slots_.size(); }
    Work GetWork() const { return work_; }

private:
    struct Slot {
        Key key;
        std::uint32_t id = 0;
    };
    std::size_t Locate(Key key) const {
        auto index = KeyHash {}(key) & (slots_.size() - 1);
        while (slots_[index].id && !(slots_[index].key == key))
            index = (index + 1) & (slots_.size() - 1);
        return index;
    }
    void Grow() {
        auto old = std::move(slots_);
        slots_ = decltype(slots_)(old.size() * 2, old.get_allocator());
        for (const auto& slot : old)
            if (slot.id) slots_[Locate(slot.key)] = slot;
        if constexpr (Track) ++work_.rehashes;
    }
    std::vector<Slot, Allocator<Slot, Track>> slots_;
    std::deque<Value, Allocator<Value, Track>> states_;
    Work work_;
};
} // namespace hashmap_lab::states
#endif
