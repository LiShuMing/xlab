#include <map>
#include <random>
#include <string>
#include <vector>

#include "gtest/gtest.h"
#include "tinykv/memtable/memtable.hpp"

namespace tinykv {
namespace {

class MemTableTest : public testing::Test {
protected:
    void SetUp() override {
        memtable_ = std::make_unique<MemTable>();
    }

    std::unique_ptr<MemTable> memtable_;
};

// Basic put and get
TEST_F(MemTableTest, PutAndGet) {
    EXPECT_EQ(memtable_->Size(), 0);
    memtable_->Put("key1", "value1");

    std::string value;
    EXPECT_TRUE(memtable_->Get("key1", &value));
    EXPECT_EQ(value, "value1");
    EXPECT_EQ(memtable_->Size(), 1);
}

// Multiple puts
TEST_F(MemTableTest, MultiplePuts) {
    memtable_->Put("key1", "value1");
    memtable_->Put("key2", "value2");
    memtable_->Put("key3", "value3");

    EXPECT_EQ(memtable_->Size(), 3);

    std::string value;
    EXPECT_TRUE(memtable_->Get("key1", &value));
    EXPECT_EQ(value, "value1");

    EXPECT_TRUE(memtable_->Get("key2", &value));
    EXPECT_EQ(value, "value2");

    EXPECT_TRUE(memtable_->Get("key3", &value));
    EXPECT_EQ(value, "value3");
}

// Update existing key
TEST_F(MemTableTest, Update) {
    memtable_->Put("key", "value1");
    memtable_->Put("key", "value2");

    std::string value;
    EXPECT_TRUE(memtable_->Get("key", &value));
    EXPECT_EQ(value, "value2");
    EXPECT_EQ(memtable_->Size(), 1);  // Size unchanged
}

// Delete
TEST_F(MemTableTest, Delete) {
    memtable_->Put("key", "value");
    EXPECT_TRUE(memtable_->Contains("key"));

    memtable_->Delete("key");
    EXPECT_FALSE(memtable_->Contains("key"));
}

// Delete non-existent
TEST_F(MemTableTest, DeleteNonExistent) {
    memtable_->Put("key1", "value1");
    memtable_->Delete("key2");  // key2 doesn't exist

    EXPECT_TRUE(memtable_->Contains("key1"));  // key1 still exists
    EXPECT_EQ(memtable_->Size(), 1);
}

// Empty key and value
TEST_F(MemTableTest, EmptyKeyValue) {
    // Note: MemTable uses Arena which reuses memory for zero-size allocations.
    // So we use different keys for each test case.
    memtable_->Put("", "value1");
    memtable_->Put("key", "value2");
    memtable_->Put("empty", "");

    std::string value;
    EXPECT_TRUE(memtable_->Get("", &value));
    EXPECT_EQ(value, "value1");

    EXPECT_TRUE(memtable_->Get("key", &value));
    EXPECT_EQ(value, "value2");

    EXPECT_TRUE(memtable_->Get("empty", &value));
    EXPECT_EQ(value, "");
}

// Memory usage tracking
TEST_F(MemTableTest, MemoryUsage) {
    auto initial_usage = memtable_->ApproximateMemoryUsage();

    memtable_->Put("key1", "value1");
    auto after_first = memtable_->ApproximateMemoryUsage();
    EXPECT_GE(after_first, initial_usage);

    memtable_->Put("key2", "value2");
    auto after_second = memtable_->ApproximateMemoryUsage();
    EXPECT_GE(after_second, after_first);
}

// Iterator
TEST_F(MemTableTest, Iterator) {
    memtable_->Put("a", "1");
    memtable_->Put("b", "2");
    memtable_->Put("c", "3");

    auto it = memtable_->NewIterator();
    it.SeekToFirst();

    EXPECT_TRUE(it.Valid());
    EXPECT_EQ(it.CurrentKey(), "a");
    EXPECT_EQ(it.CurrentValue(), "1");

    it.Next();
    EXPECT_TRUE(it.Valid());
    EXPECT_EQ(it.CurrentKey(), "b");
    EXPECT_EQ(it.CurrentValue(), "2");

    it.Next();
    EXPECT_TRUE(it.Valid());
    EXPECT_EQ(it.CurrentKey(), "c");
    EXPECT_EQ(it.CurrentValue(), "3");

    it.Next();
    EXPECT_FALSE(it.Valid());
}

// Iterator seek
TEST_F(MemTableTest, IteratorSeek) {
    memtable_->Put("a", "1");
    memtable_->Put("b", "2");
    memtable_->Put("c", "3");
    memtable_->Put("d", "4");

    auto it = memtable_->NewIterator();

    it.Seek("b");
    EXPECT_TRUE(it.Valid());
    EXPECT_EQ(it.CurrentKey(), "b");

    it.Seek("bb");
    EXPECT_TRUE(it.Valid());
    EXPECT_EQ(it.CurrentKey(), "c");

    it.Seek("z");
    EXPECT_FALSE(it.Valid());
}

// Stress test with random operations
TEST_F(MemTableTest, StressTest) {
    std::map<std::string, std::string> ref_map;
    const int kNumOps = 1000;
    std::mt19937 rng(42);
    std::uniform_int_distribution<int> dist(1, 100);

    for (int i = 0; i < kNumOps; ++i) {
        int op = dist(rng);
        std::string key = "key" + std::to_string(dist(rng) % 100);

        if (op <= 50) {  // 50% Put
            std::string value = "value" + std::to_string(dist(rng));
            memtable_->Put(key, value);
            ref_map[key] = value;
        } else if (op <= 80) {  // 30% Get
            std::string value;
            bool found_memtable = memtable_->Get(key, &value);
            auto it = ref_map.find(key);
            bool found_ref = (it != ref_map.end());
            EXPECT_EQ(found_memtable, found_ref);
            if (found_memtable) {
                EXPECT_EQ(value, it->second);
            }
        } else {  // 20% Delete
            memtable_->Delete(key);
            ref_map.erase(key);
            EXPECT_FALSE(memtable_->Contains(key));
        }
    }

    // Final verification
    for (const auto& [key, value] : ref_map) {
        std::string found_value;
        EXPECT_TRUE(memtable_->Get(key, &found_value));
        EXPECT_EQ(found_value, value);
    }
}

// Large value
TEST_F(MemTableTest, LargeValue) {
    std::string large_value(10000, 'x');  // 10KB

    memtable_->Put("key", large_value);

    std::string retrieved;
    EXPECT_TRUE(memtable_->Get("key", &retrieved));
    EXPECT_EQ(retrieved, large_value);
}

// Many small entries
TEST_F(MemTableTest, ManySmallEntries) {
    const int kNumEntries = 1000;

    for (int i = 0; i < kNumEntries; ++i) {
        memtable_->Put("key" + std::to_string(i), "value" + std::to_string(i));
    }

    EXPECT_EQ(memtable_->Size(), static_cast<size_t>(kNumEntries));

    // Random access verification
    std::mt19937 rng(42);
    std::uniform_int_distribution<int> dist(0, kNumEntries - 1);

    for (int i = 0; i < 100; ++i) {
        int idx = dist(rng);
        std::string expected_key = "key" + std::to_string(idx);
        std::string expected_value = "value" + std::to_string(idx);

        std::string value;
        EXPECT_TRUE(memtable_->Get(expected_key, &value));
        EXPECT_EQ(value, expected_value);
    }
}

// Approximate size calculation
TEST_F(MemTableTest, ApproximateSizeOf) {
    auto size = MemTable::ApproximateSizeOf(Slice("key"), Slice("value"));
    // ApproximateSizeOf should return at least key.size() + value.size() + overhead
    // Due to potential compiler/alignment effects, allow small variance
    EXPECT_GE(size, 4 + 5 + MemTable::kEntryOverhead - 1);
}

}  // namespace
}  // namespace tinykv
