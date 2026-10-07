#include "tinykv/memtable/arena.hpp"

#include <algorithm>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <stdexcept>
#include <utility>

namespace tinykv {

Arena::Arena() = default;

Arena::~Arena() {
    // Free all blocks (each block includes header and data in one allocation)
    Block* block = current_block_;
    while (block != nullptr) {
        Block* prev = block->prev;
        std::free(block); // Free entire block (header + data)
        block = prev;
    }
}

Arena::Arena(Arena&& other) noexcept
        : current_block_(other.current_block_),
          current_(other.current_),
          limit_(other.limit_),
          memory_usage_(other.memory_usage_) {
    other.current_block_ = nullptr;
    other.current_ = nullptr;
    other.limit_ = nullptr;
    other.memory_usage_ = 0;
}

Arena& Arena::operator=(Arena&& other) noexcept {
    if (this != &other) {
        Arena moved(std::move(other));
        std::swap(current_block_, moved.current_block_);
        std::swap(current_, moved.current_);
        std::swap(limit_, moved.limit_);
        std::swap(memory_usage_, moved.memory_usage_);
    }
    return *this;
}

auto Arena::AlignUp(char* ptr, size_t alignment) -> char* {
    // alignment must be power of 2
    uintptr_t addr = reinterpret_cast<uintptr_t>(ptr);
    size_t misaligned = addr & (alignment - 1);
    if (misaligned == 0) {
        return ptr;
    }
    return reinterpret_cast<char*>(addr + (alignment - misaligned));
}

auto Arena::AllocateBlock(size_t size) -> Block* {
    // Allocate block header and data together
    size_t block_size = sizeof(Block) + size;
    Block* block = static_cast<Block*>(std::malloc(block_size));
    if (block == nullptr) {
        throw std::bad_alloc();
    }

    block->data = reinterpret_cast<char*>(block) + sizeof(Block);
    block->size = size;
    block->prev = current_block_;

    return block;
}

auto Arena::Allocate(size_t bytes) -> char* {
    return AllocateAligned(bytes, alignof(std::max_align_t));
}

auto Arena::AllocateAligned(size_t bytes, size_t alignment) -> char* {
    if (alignment == 0 || (alignment & (alignment - 1)) != 0) {
        throw std::invalid_argument("alignment must be a nonzero power of 2");
    }
    if (bytes == 0) {
        return nullptr;
    }

    if (current_block_ != nullptr) {
        size_t available = static_cast<size_t>(limit_ - current_);
        size_t misaligned = reinterpret_cast<uintptr_t>(current_) & (alignment - 1);
        size_t padding = (alignment - misaligned) & (alignment - 1);
        if (padding <= available && bytes <= available - padding) {
            char* result = current_ + padding;
            current_ = result + bytes;
            return result;
        }
    }
    size_t payload_size = std::max(bytes, kBlockSize);
    if (alignment - 1 > std::numeric_limits<size_t>::max() - sizeof(Block) ||
        payload_size > std::numeric_limits<size_t>::max() - sizeof(Block) - (alignment - 1)) {
        throw std::bad_alloc();
    }
    size_t block_size = payload_size + alignment - 1;
    Block* block = AllocateBlock(block_size);
    current_block_ = block;

    // Align the first allocation within the block
    char* result = AlignUp(block->data, alignment);
    current_ = result + bytes;
    limit_ = block->data + block->size;

    memory_usage_ += sizeof(Block) + block_size;

    return result;
}

} // namespace tinykv
