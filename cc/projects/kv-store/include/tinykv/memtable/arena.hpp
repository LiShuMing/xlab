#ifndef TINYKV_MEMTABLE_ARENA_HPP_
#define TINYKV_MEMTABLE_ARENA_HPP_

#include <cstddef>
#include <cstdint>
#include <memory>
#include <new>

namespace tinykv {

// Arena: a simple memory pool for high-frequency small allocations.
// Reduces malloc overhead by allocating large blocks and handing out
// sequential slices from within them.
//
// Thread-safety: Not thread-safe. Caller must synchronize.
class Arena {
public:
    Arena();
    ~Arena();

    // Non-copyable, movable
    Arena(const Arena&) = delete;
    Arena& operator=(const Arena&) = delete;
    Arena(Arena&&) noexcept;
    Arena& operator=(Arena&&) noexcept;

    // Allocate bytes with natural alignment.
    // Returns nullptr if bytes == 0.
    auto Allocate(size_t bytes) -> char*;

    // Allocate bytes with specified alignment.
    // alignment must be power of 2.
    auto AllocateAligned(size_t bytes, size_t alignment) -> char*;

    // Allocate space for an object, construct in-place.
    template<typename T, typename... Args>
    auto Allocate(Args&&... args) -> T* {
        void* buf = AllocateAligned(sizeof(T), alignof(T));
        return new (buf) T(std::forward<Args>(args)...);
    }

    // Allocate memory for a node with variable-sized array (e.g., SkipList Node)
    // size: base size of the struct
    // array_elem_size: size of each array element
    // array_count: number of elements in the array
    auto AllocateNode(size_t base_size, size_t array_elem_size, int array_count) -> char* {
        size_t total_size = base_size + array_elem_size * array_count;
        char* buf = AllocateAligned(total_size, alignof(max_align_t));
        return buf;
    }

    // Total memory allocated from the system.
    auto MemoryUsage() const -> size_t { return memory_usage_; }

    // Approximate memory used (for reporting, not precise).
    auto ApproximateMemoryUsage() const -> size_t { return memory_usage_; }

private:
    // Block allocation size - large enough to reduce malloc frequency,
    // but not too large to waste memory.
    static constexpr size_t kBlockSize = 4096;

    // Minimum allocation alignment for aligned allocations.
    static constexpr size_t kAlignment = 8;

    struct Block {
        Block* prev;
        char* data;
        size_t size;
    };

    // Current block being allocated from
    Block* current_block_ = nullptr;
    // Pointer to next free byte in current block
    char* current_ = nullptr;
    // End of current block
    char* limit_ = nullptr;
    // Total memory allocated
    size_t memory_usage_ = 0;

    // Allocate a new block of at least the requested size.
    auto AllocateBlock(size_t size) -> Block*;

    // Helper to advance current_ to aligned position.
    auto AlignUp(char* ptr, size_t alignment) -> char*;
};

}  // namespace tinykv

#endif  // TINYKV_MEMTABLE_ARENA_HPP_
