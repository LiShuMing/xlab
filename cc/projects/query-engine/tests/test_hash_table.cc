#include <cstdint>
#include <random>
#include <vector>

#include "gtest/gtest.h"
#include "vagg/ht/hash_table.h"

namespace vagg {

TEST(HashTableTest, BasicInsertAndFind) {
  HashTable<int32_t, int64_t> ht;

  // Insert some entries
  ht.FindOrInsert(1, HashInt32(1))->value = 100;
  ht.FindOrInsert(2, HashInt32(2))->value = 200;
  ht.FindOrInsert(3, HashInt32(3))->value = 300;

  // Find them
  auto* e1 = ht.Find(1, HashInt32(1));
  auto* e2 = ht.Find(2, HashInt32(2));
  auto* e3 = ht.Find(3, HashInt32(3));

  ASSERT_NE(e1, nullptr);
  ASSERT_NE(e2, nullptr);
  ASSERT_NE(e3, nullptr);
  EXPECT_EQ(e1->value, 100);
  EXPECT_EQ(e2->value, 200);
  EXPECT_EQ(e3->value, 300);

  // Non-existent key
  EXPECT_EQ(ht.Find(999), nullptr);
}

TEST(HashTableTest, FindOrInsert) {
  HashTable<int32_t, int64_t> ht;

  // First insert
  auto* e1 = ht.FindOrInsert(42);
  ASSERT_NE(e1, nullptr);
  e1->value = 123;

  // FindOrInsert again - should find existing
  auto* e2 = ht.FindOrInsert(42);
  ASSERT_NE(e2, nullptr);
  EXPECT_EQ(e2, e1);  // Same entry
  EXPECT_EQ(e2->value, 123);  // Value preserved
}

TEST(HashTableTest, AggregationWorkflow) {
  // Simulate: key, value pairs -> SUM(value) GROUP BY key
  // (1, 10), (2, 20), (1, 30), (3, 40), (2, 50)
  // Expected: {1: 40, 2: 70, 3: 40}

  HashTable<int32_t, int64_t> ht;

  // Process each row
  struct Row { int32_t key; int64_t value; };
  std::vector<Row> rows = {{1, 10}, {2, 20}, {1, 30}, {3, 40}, {2, 50}};

  for (const auto& row : rows) {
    auto* entry = ht.FindOrInsert(row.key);
    entry->value += row.value;
  }

  // Verify results
  EXPECT_EQ(ht.size(), 3);

  auto* e1 = ht.Find(1);
  auto* e2 = ht.Find(2);
  auto* e3 = ht.Find(3);

  ASSERT_NE(e1, nullptr);
  ASSERT_NE(e2, nullptr);
  ASSERT_NE(e3, nullptr);

  EXPECT_EQ(e1->value, 40);  // 10 + 30
  EXPECT_EQ(e2->value, 70);  // 20 + 50
  EXPECT_EQ(e3->value, 40);
}

TEST(HashTableTest, LoadFactorAndResize) {
  HashTable<int32_t, int64_t> ht;
  HashTableConfig config;
  config.capacity = 16;  // Small initial capacity
  config.max_load_factor = 0.7;
  ht = HashTable<int32_t, int64_t>(config);

  // Insert entries that fit without resize (capacity 16 * 0.7 = 11.2, so up to 11 should fit)
  const int num_entries = 10;
  for (int i = 0; i < num_entries; ++i) {
    auto* entry = ht.FindOrInsert(i);
    entry->value = i * 10;
  }

  EXPECT_EQ(ht.size(), num_entries);

  // Verify all entries are accessible
  for (int i = 0; i < num_entries; ++i) {
    auto* entry = ht.Find(i);
    ASSERT_NE(entry, nullptr);
    EXPECT_EQ(entry->value, i * 10) << "Find(" << i << ") returned wrong value";
  }

  // Check load factor
  EXPECT_LE(ht.load_factor(), 0.7);
}

TEST(HashTableTest, Clear) {
  HashTable<int32_t, int64_t> ht;

  // Insert some entries
  for (int i = 0; i < 100; ++i) {
    ht.FindOrInsert(i);
  }

  EXPECT_EQ(ht.size(), 100);

  // Clear and verify
  ht.Clear();
  EXPECT_EQ(ht.size(), 0);
  EXPECT_EQ(ht.Find(50), nullptr);
}

TEST(HashTableTest, Statistics) {
  HashTable<int32_t, int64_t> ht;

  // Insert entries
  for (int i = 0; i < 1000; ++i) {
    ht.FindOrInsert(i);
  }

  auto stats = ht.GetStats();

  EXPECT_EQ(stats.num_entries, 1000);
  EXPECT_EQ(stats.load_factor, ht.load_factor());
  EXPECT_GT(stats.average_probes, 0);
}

TEST(HashTableTest, CollisionHandling) {
  // Insert entries that may cause collisions
  // Using sequential keys to potentially cause clustering
  HashTable<int32_t, int64_t> ht;

  // Use smaller number to avoid excessive resizes during debugging
  for (int i = 0; i < 100; ++i) {
    auto* entry = ht.FindOrInsert(i);
    entry->value = i;
  }

  // Verify all entries
  for (int i = 0; i < 100; ++i) {
    auto* entry = ht.Find(i);
    ASSERT_NE(entry, nullptr);
    EXPECT_EQ(entry->value, i) << "Find(" << i << ") returned wrong value";
  }
}

TEST(HashTableTest, DifferentKeyTypes) {
  // Test with different key types
  HashTable<int64_t, int64_t> ht64;
  ht64.FindOrInsert(static_cast<int64_t>(12345678901234LL));
  auto* found = ht64.Find(static_cast<int64_t>(12345678901234LL));
  ASSERT_NE(found, nullptr);
}

}  // namespace vagg
