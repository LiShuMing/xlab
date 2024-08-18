#include "tinykv/memtable/arena.hpp"

#include <cstdlib>
#include <cstring>

namespace tinykv {

Arena::Arena() = default;

Arena::~Arena() {
    // Free all blocks (each block includes header and data in one allocation)
    Block* block = current_block_;
    while (block != nullptr) {
        Block* prev = block->prev;
        std::free(block);  // Free entire block (header + data)
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
        // Free existing blocks
        this->~Arena();

        // Move state
        current_block_ = other.current_block_;
        current_ = other.current_;
        limit_ = other.limit_;
        memory_usage_ = other.memory_usage_;

        // Reset source
        other.current_block_ = nullptr;
        other.current_ = nullptr;
        other.limit_ = nullptr;
        other.memory_usage_ = 0;
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
    if (bytes == 0) {
        return nullptr;
    }

    // Simple case: fits in current block
    if (current_block_ != nullptr && current_ + bytes <= limit_) {
        char* result = current_;
        current_ += bytes;
        return result;
    }

    // Need to allocate a new block
    return AllocateAligned(bytes, kAlignment);
}

auto Arena::AllocateAligned(size_t bytes, size_t alignment) -> char* {
    if (bytes == 0) {
        return nullptr;
    }

    // Allocate new block large enough for request plus potential waste
    size_t block_size = (bytes + alignment - 1) + kBlockSize;
    Block* block = AllocateBlock(block_size);
    current_block_ = block;

    // Align the first allocation within the block
    char* result = AlignUp(block->data, alignment);
    current_ = result + bytes;
    limit_ = block->data + block->size;

    memory_usage_ += block_size;

    return result;
}

}  // namespace tinykv
