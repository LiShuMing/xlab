#ifndef CACHE_LAB_POLICIES_H_
#define CACHE_LAB_POLICIES_H_

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <list>
#include <map>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

namespace cache_lab {
using Key = std::uint64_t;
inline std::uint64_t Mix(std::uint64_t value) {
    value = (value ^ (value >> 30)) * 0xbf58476d1ce4e5b9ULL;
    value = (value ^ (value >> 27)) * 0x94d049bb133111ebULL;
    return value ^ (value >> 31);
}
struct Hash {
    std::size_t operator()(Key key) const { return Mix(key); }
};
struct Events {
    std::uint64_t admissions = 0, evictions = 0, rejections = 0;
    std::uint64_t promotions = 0, demotions = 0, resets = 0, ghost_hits = 0;
};
struct Layout {
    std::size_t resident = 0, history = 0, sketch_bytes = 0;
    std::size_t window = 0, probation = 0, protected_size = 0, arc_target = 0;
};

// MRU at front. Every policy uses the same unordered-map + list building block.
class Queue {
public:
    bool Contains(Key key) const { return index_.find(key) != index_.end(); }
    void Insert(Key key) {
        if (Contains(key)) throw std::logic_error("duplicate queue entry");
        keys_.push_front(key);
        index_.emplace(key, keys_.begin());
    }
    void Erase(Key key) {
        auto it = index_.find(key);
        if (it == index_.end()) throw std::logic_error("missing queue entry");
        keys_.erase(it->second);
        index_.erase(it);
    }
    void Touch(Key key) { keys_.splice(keys_.begin(), keys_, index_.at(key)); }
    Key Oldest() const {
        if (keys_.empty()) throw std::logic_error("empty queue victim");
        return keys_.back();
    }
    Key Pop() {
        auto key = Oldest();
        Erase(key);
        return key;
    }
    std::size_t Size() const { return keys_.size(); }
    std::vector<Key> Keys() const { return {keys_.begin(), keys_.end()}; }
    Queue() = default;
    Queue(const Queue&) = delete;
    Queue& operator=(const Queue&) = delete;

private:
    std::list<Key> keys_;
    std::unordered_map<Key, std::list<Key>::iterator, Hash> index_;
};

template <bool Recency>
class Simple {
public:
    explicit Simple(std::size_t capacity) : capacity_(capacity) {}
    bool Access(Key key) {
        if (queue_.Contains(key)) {
            if constexpr (Recency) queue_.Touch(key);
            return true;
        }
        if (capacity_) {
            if (queue_.Size() == capacity_) {
                queue_.Pop();
                ++events_.evictions;
            }
            queue_.Insert(key);
            ++events_.admissions;
        }
        return false;
    }
    Layout GetLayout() const { return {queue_.Size()}; }
    Events GetEvents() const { return events_; }
    std::vector<Key> Resident() const { return queue_.Keys(); }

private:
    std::size_t capacity_;
    Queue queue_;
    Events events_;
};
using Fifo = Simple<false>;
using Lru = Simple<true>;

// Exact resident-only LFU, with LRU tie breaking and no frequency decay.
class Lfu {
public:
    explicit Lfu(std::size_t capacity) : capacity_(capacity) {}
    bool Access(Key key) {
        auto it = frequencies_.find(key);
        if (it != frequencies_.end()) {
            auto frequency = it->second;
            buckets_.at(frequency).Erase(key);
            if (!buckets_.at(frequency).Size()) buckets_.erase(frequency);
            buckets_[frequency + 1].Insert(key);
            ++it->second;
            return true;
        }
        if (capacity_) {
            if (frequencies_.size() == capacity_) {
                auto victim = buckets_.begin();
                frequencies_.erase(victim->second.Pop());
                if (!victim->second.Size()) buckets_.erase(victim);
                ++events_.evictions;
            }
            frequencies_.emplace(key, 1);
            buckets_[1].Insert(key);
            ++events_.admissions;
        }
        return false;
    }
    Layout GetLayout() const { return {frequencies_.size()}; }
    Events GetEvents() const { return events_; }
    std::vector<Key> Resident() const {
        std::vector<Key> result;
        for (const auto& item : frequencies_) result.push_back(item.first);
        return result;
    }

private:
    std::size_t capacity_;
    std::unordered_map<Key, std::uint64_t, Hash> frequencies_;
    std::map<std::uint64_t, Queue> buckets_;
    Events events_;
};

class Segmented {
public:
    Segmented(std::size_t capacity, unsigned protected_percent)
            : capacity_(capacity), protected_capacity_(capacity * protected_percent / 100) {
        if (protected_percent > 95) throw std::invalid_argument("protected ratio exceeds 95%");
    }
    bool Hit(Key key) {
        if (protected_.Contains(key)) {
            protected_.Touch(key);
            return true;
        }
        if (!probation_.Contains(key)) return false;
        probation_.Erase(key);
        protected_.Insert(key);
        ++events_.promotions;
        if (protected_.Size() > protected_capacity_) {
            probation_.Insert(protected_.Pop());
            ++events_.demotions;
        }
        return true;
    }
    void Admit(Key key) { probation_.Insert(key); }
    Key Victim() const { return probation_.Oldest(); }
    void Evict() {
        probation_.Pop();
        ++events_.evictions;
    }
    bool Full() const { return Size() == capacity_; }
    std::size_t Size() const { return probation_.Size() + protected_.Size(); }
    Layout GetLayout() const {
        Layout layout;
        layout.resident = Size();
        layout.probation = probation_.Size();
        layout.protected_size = protected_.Size();
        return layout;
    }
    Events GetEvents() const { return events_; }
    std::vector<Key> Resident() const {
        auto result = probation_.Keys(), other = protected_.Keys();
        result.insert(result.end(), other.begin(), other.end());
        return result;
    }

private:
    std::size_t capacity_, protected_capacity_;
    Queue probation_, protected_;
    Events events_;
};
class Slru {
public:
    Slru(std::size_t capacity, unsigned protected_percent = 80)
            : capacity_(capacity), main_(capacity, protected_percent) {}
    bool Access(Key key) {
        if (main_.Hit(key)) return true;
        if (capacity_) {
            if (main_.Full()) main_.Evict();
            main_.Admit(key);
            ++admissions_;
        }
        return false;
    }
    Layout GetLayout() const { return main_.GetLayout(); }
    Events GetEvents() const {
        auto e = main_.GetEvents();
        e.admissions = admissions_;
        return e;
    }
    std::vector<Key> Resident() const { return main_.Resident(); }

private:
    std::size_t capacity_;
    Segmented main_;
    std::uint64_t admissions_ = 0;
};

// Four independent rows of packed 4-bit count-min counters; reset by request count.
class Sketch {
public:
    Sketch(std::size_t capacity, unsigned aging_factor)
            : interval_(std::max(std::size_t {1}, capacity * aging_factor)) {
        if (!aging_factor || aging_factor > 100)
            throw std::invalid_argument("invalid sketch aging");
        while (width_ < std::max(std::size_t {64}, capacity * 4)) width_ *= 2;
        counters_.resize(width_ * 2, 0);
    }
    bool Record(Key key) {
        for (std::size_t row = 0; row < 4; ++row) {
            auto index = Index(key, row), shift = (index & 1) * 4;
            auto& byte = counters_[index / 2];
            if (((byte >> shift) & 15) < 15) byte += 1U << shift;
        }
        if (++samples_ < interval_) return false;
        for (auto& byte : counters_) byte = (byte >> 1) & 0x77;
        samples_ = 0;
        return true;
    }
    unsigned Estimate(Key key) const {
        unsigned result = 15;
        for (std::size_t row = 0; row < 4; ++row) {
            auto index = Index(key, row);
            result = std::min(result, unsigned((counters_[index / 2] >> ((index & 1) * 4)) & 15));
        }
        return result;
    }
    std::size_t Bytes() const { return counters_.size(); }

private:
    std::size_t Index(Key key, std::size_t row) const {
        static constexpr std::array<Key, 4> seeds {0x243f6a8885a308d3ULL, 0x13198a2e03707344ULL,
                                                   0xa4093822299f31d0ULL, 0x082efa98ec4e6c89ULL};
        return row * width_ + (Mix(key ^ seeds[row]) & (width_ - 1));
    }
    std::size_t width_ = 1, interval_, samples_ = 0;
    std::vector<std::uint8_t> counters_;
};
class WTinyLfu {
public:
    WTinyLfu(std::size_t capacity, unsigned window_percent = 1, unsigned protected_percent = 80,
             unsigned aging_factor = 10)
            : capacity_(capacity),
              window_capacity_(capacity ? std::max(std::size_t {1}, capacity * window_percent / 100)
                                        : 0),
              main_(capacity - window_capacity_, protected_percent),
              sketch_(capacity, aging_factor) {
        if (!window_percent || window_percent > 50)
            throw std::invalid_argument("window ratio must be 1..50%");
    }
    bool Access(Key key) {
        if (sketch_.Record(key)) ++events_.resets;
        if (window_.Contains(key)) {
            window_.Touch(key);
            return true;
        }
        if (main_.Hit(key)) return true;
        if (!capacity_) return false;
        ++events_.admissions;
        if (window_.Size() == window_capacity_) {
            auto candidate = window_.Pop();
            window_.Insert(key);
            if (capacity_ == window_capacity_) {
                ++events_.evictions;
                return false;
            }
            if (!main_.Full())
                main_.Admit(candidate);
            else if (sketch_.Estimate(candidate) > sketch_.Estimate(main_.Victim())) {
                main_.Evict();
                main_.Admit(candidate);
            } else {
                ++events_.rejections;
                ++events_.evictions;
            }
        } else
            window_.Insert(key);
        return false;
    }
    Layout GetLayout() const {
        auto layout = main_.GetLayout();
        layout.window = window_.Size();
        layout.resident += layout.window;
        layout.sketch_bytes = sketch_.Bytes();
        return layout;
    }
    Events GetEvents() const {
        auto result = events_, main = main_.GetEvents();
        result.evictions += main.evictions;
        result.promotions = main.promotions;
        result.demotions = main.demotions;
        return result;
    }
    std::vector<Key> Resident() const {
        auto result = main_.Resident(), other = window_.Keys();
        result.insert(result.end(), other.begin(), other.end());
        return result;
    }

private:
    std::size_t capacity_, window_capacity_;
    Queue window_;
    Segmented main_;
    Sketch sketch_;
    Events events_;
};

// Canonical ARC: T1/T2 residents, B1/B2 key-only ghosts, one total resident capacity.
class Arc {
public:
    explicit Arc(std::size_t capacity) : capacity_(capacity) {}
    bool Access(Key key) {
        if (t1_.Contains(key)) {
            t1_.Erase(key);
            t2_.Insert(key);
            ++events_.promotions;
            return true;
        }
        if (t2_.Contains(key)) {
            t2_.Touch(key);
            return true;
        }
        if (!capacity_) return false;
        ++events_.admissions;
        if (b1_.Contains(key)) {
            target_ = std::min(capacity_,
                               target_ + std::max(std::size_t {1}, b2_.Size() / b1_.Size()));
            Replace(false);
            b1_.Erase(key);
            t2_.Insert(key);
            ++events_.ghost_hits;
        } else if (b2_.Contains(key)) {
            auto change = std::max(std::size_t {1}, b1_.Size() / b2_.Size());
            target_ = target_ > change ? target_ - change : 0;
            Replace(true);
            b2_.Erase(key);
            t2_.Insert(key);
            ++events_.ghost_hits;
        } else {
            if (t1_.Size() + b1_.Size() == capacity_) {
                if (t1_.Size() < capacity_) {
                    b1_.Pop();
                    Replace(false);
                } else {
                    t1_.Pop();
                    ++events_.evictions;
                }
            } else if (t1_.Size() + t2_.Size() + b1_.Size() + b2_.Size() >= capacity_) {
                if (t1_.Size() + t2_.Size() + b1_.Size() + b2_.Size() == 2 * capacity_) b2_.Pop();
                Replace(false);
            }
            t1_.Insert(key);
        }
        return false;
    }
    Layout GetLayout() const {
        Layout layout;
        layout.resident = t1_.Size() + t2_.Size();
        layout.history = b1_.Size() + b2_.Size();
        layout.arc_target = target_;
        layout.probation = t1_.Size();
        layout.protected_size = t2_.Size();
        return layout;
    }
    Events GetEvents() const { return events_; }
    std::vector<Key> Resident() const {
        auto result = t1_.Keys(), other = t2_.Keys();
        result.insert(result.end(), other.begin(), other.end());
        return result;
    }

private:
    void Replace(bool b2_hit) {
        if (t1_.Size() && (t1_.Size() > target_ || (b2_hit && t1_.Size() == target_)))
            b1_.Insert(t1_.Pop());
        else
            b2_.Insert(t2_.Pop());
        ++events_.evictions;
    }
    std::size_t capacity_, target_ = 0;
    Queue t1_, t2_, b1_, b2_;
    Events events_;
};
} // namespace cache_lab
#endif
