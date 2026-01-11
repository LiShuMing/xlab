#ifndef TINYKV_COMMON_SLICE_HPP_
#define TINYKV_COMMON_SLICE_HPP_

#include <cstddef>
#include <cstring>
#include <string>
#include <string_view>

namespace tinykv {

// Slice: a non-owning reference to a byte sequence.
// Used throughout the API to avoid copying string data.
class Slice {
public:
    // Constructors
    Slice() noexcept : data_(""), size_(0) {}
    Slice(const char* data, size_t size) noexcept : data_(data), size_(size) {}
    Slice(const char* str) noexcept : data_(str), size_(str ? std::strlen(str) : 0) {}
    Slice(const std::string& s) noexcept : data_(s.data()), size_(s.size()) {}
    explicit Slice(std::string_view sv) noexcept : data_(sv.data()), size_(sv.size()) {}

    // Copyable (shallow copy - does not own data)
    Slice(const Slice&) noexcept = default;
    Slice& operator=(const Slice&) noexcept = default;

    // Movable
    Slice(Slice&&) noexcept = default;
    Slice& operator=(Slice&&) noexcept = default;

    // Accessors
    auto data() const noexcept -> const char* { return data_; }
    auto size() const noexcept -> size_t { return size_; }
    auto empty() const noexcept -> bool { return size_ == 0; }

    // Byte access - no bounds checking
    auto operator[](size_t n) const noexcept -> char { return data_[n]; }

    // Comparison operators
    auto operator==(const Slice& other) const noexcept -> bool {
        return size_ == other.size_ && std::memcmp(data_, other.data_, size_) == 0;
    }
    auto operator!=(const Slice& other) const noexcept -> bool { return !(*this == other); }
    auto operator<(const Slice& other) const noexcept -> bool { return Compare(other) < 0; }
    auto operator>(const Slice& other) const noexcept -> bool { return Compare(other) > 0; }
    auto operator<=(const Slice& other) const noexcept -> bool { return Compare(other) <= 0; }
    auto operator>=(const Slice& other) const noexcept -> bool { return Compare(other) >= 0; }

    // Three-way comparison
    // Returns: -1 if this < other, 0 if equal, +1 if this > other
    auto Compare(const Slice& other) const noexcept -> int {
        size_t min_size = size_ < other.size_ ? size_ : other.size_;
        int cmp = std::memcmp(data_, other.data_, min_size);
        if (cmp != 0) return cmp < 0 ? -1 : 1;
        if (size_ == other.size_) return 0;
        return size_ < other.size_ ? -1 : 1;
    }

    // Remove the first `n` bytes (must be <= size())
    void RemovePrefix(size_t n) noexcept {
        if (n <= size_) {
            data_ += n;
            size_ -= n;
        }
    }

    // Remove the last `n` bytes (must be <= size())
    void RemoveSuffix(size_t n) noexcept {
        if (n <= size_) {
            size_ -= n;
        }
    }

    // Convert to std::string (copies data)
    auto ToString() const -> std::string { return std::string(data_, size_); }
    explicit operator std::string() const { return ToString(); }

    // Convert to std::string_view (no copy)
    auto ToStringView() const noexcept -> std::string_view {
        return std::string_view(data_, size_);
    }

private:
    const char* data_;
    size_t size_;
};

// Hash function for Slice (for unordered containers)
struct SliceHash {
    auto operator()(const Slice& s) const noexcept -> std::size_t {
        // Simple but effective hash - FNV-1a variant
        const uint64_t FNV_offset_basis = 14695981039346656037ull;
        const uint64_t FNV_prime = 1099511628211ull;
        uint64_t hash = FNV_offset_basis;
        for (size_t i = 0; i < s.size(); ++i) {
            hash ^= static_cast<unsigned char>(s[i]);
            hash *= FNV_prime;
        }
        return static_cast<std::size_t>(hash);
    }
};

}  // namespace tinykv

#endif  // TINYKV_COMMON_SLICE_HPP_
