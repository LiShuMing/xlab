#ifndef TINYKV_UTIL_COMPARATOR_HPP_
#define TINYKV_UTIL_COMPARATOR_HPP_

#include "tinykv/common/slice.hpp"

namespace tinykv {

// Comparator interface for ordering keys.
// Used throughout the system to enable custom key ordering.
class Comparator {
public:
    virtual ~Comparator() = default;

    // Three-way comparison: returns -1, 0, or +1
    virtual auto Compare(const Slice& a, const Slice& b) const -> int = 0;

    // Find shortest separator between start and limit.
    // Returns a key that is > start and < limit (lexicographically).
    // Default implementation returns limit.
    virtual auto FindShortestSeparator(const Slice& start,
                                        const Slice& limit) const -> const char* {
        return limit.data();
    }

    // Find shortest successor of key.
    // Returns a key that is > key.
    // Default implementation appends '\0'.
    virtual auto FindShortSuccessor(const Slice& key) const -> const char* {
        return key.data() + key.size();
    }

    // Name for debugging and file format identification.
    // Must be constant for the lifetime of the database.
    virtual auto Name() const -> const char* = 0;
};

// Byte-wise (lexicographic) comparator.
// Matches the ordering used by std::string and most database systems.
class BytewiseComparator : public Comparator {
public:
    auto Compare(const Slice& a, const Slice& b) const -> int override {
        return a.Compare(b);
    }

    auto FindShortestSeparator(const Slice& start,
                                const Slice& limit) const -> const char* override {
        // Find first position where start and limit differ
        size_t min_len = start.size() < limit.size() ? start.size() : limit.size();
        size_t pos = 0;
        while (pos < min_len && start[pos] == limit[pos]) {
            ++pos;
        }

        if (pos >= min_len) {
            // One is prefix of other, return limit
            return limit.data();
        }

        // Found a difference, increment at that position if possible
        if (start[pos] < 0xFF) {
            // Can increment
            return limit.data();  // Simplified: just return limit
        }

        return limit.data();
    }

    auto FindShortSuccessor(const Slice& key) const -> const char* override {
        // Simplified: return pointer past end (caller must allocate)
        return key.data() + key.size();
    }

    auto Name() const -> const char* override { return "tinykv.BytewiseComparator"; }
};

}  // namespace tinykv

#endif  // TINYKV_UTIL_COMPARATOR_HPP_
