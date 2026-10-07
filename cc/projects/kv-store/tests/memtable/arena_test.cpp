#include "tinykv/memtable/arena.hpp"

#include <gtest/gtest.h>

#include <cstddef>
#include <cstdint>
#include <limits>
#include <utility>

#include "tinykv/memtable/memtable.hpp"

TEST(ArenaTest, OddSizedAllocationsKeepNaturalAlignment) {
    tinykv::Arena arena;
    for (size_t size = 1; size < 100; ++size) {
        auto address = reinterpret_cast<uintptr_t>(arena.Allocate(size));
        EXPECT_EQ(address % alignof(std::max_align_t), 0);
    }
}

TEST(ArenaTest, AlignedAllocationsReuseBlocks) {
    tinykv::Arena arena;
    arena.AllocateAligned(8, 8);
    size_t initial_usage = arena.MemoryUsage();
    for (int i = 0; i < 100; ++i) {
        auto address = reinterpret_cast<uintptr_t>(arena.AllocateAligned(8, 8));
        EXPECT_EQ(address % 8, 0);
    }
    EXPECT_EQ(arena.MemoryUsage(), initial_usage);
    EXPECT_THROW(arena.AllocateAligned(1, 3), std::invalid_argument);
    EXPECT_THROW(arena.AllocateAligned(std::numeric_limits<size_t>::max(), 8), std::bad_alloc);
}

TEST(ArenaTest, MoveAssignmentTransfersLiveAllocations) {
    tinykv::Arena source;
    char* bytes = source.Allocate(10);
    bytes[0] = 'x';
    tinykv::Arena destination;
    destination.Allocate(10);
    destination = std::move(source);
    EXPECT_EQ(bytes[0], 'x');
    EXPECT_EQ(source.MemoryUsage(), 0);
    EXPECT_GT(destination.MemoryUsage(), 0);
    EXPECT_NE(source.Allocate(10), nullptr);
}

TEST(MemTableLifecycleTest, RepeatedConstructionInitializesArenaBeforeSkipList) {
    for (int i = 0; i < 200; ++i) {
        tinykv::MemTable table;
        table.Put("key", "value");
        std::string value;
        ASSERT_TRUE(table.Get("key", &value));
        EXPECT_EQ(value, "value");
    }
}
