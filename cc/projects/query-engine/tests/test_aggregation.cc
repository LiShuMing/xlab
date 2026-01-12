#include <numeric>
#include <vector>

#include "gtest/gtest.h"
#include "vagg/ops/aggregate_op.h"
#include "vagg/ops/scan_op.h"
#include "vagg/ops/sink_op.h"

namespace vagg {

TEST(AggregationTest, SimpleSum) {
  // Create data: keys [1, 2, 1, 3, 2], values [10, 20, 30, 40, 50]
  // Expected: {1: 40, 2: 70, 3: 40}
  std::vector<int32_t> keys = {1, 2, 1, 3, 2};
  std::vector<int64_t> values = {10, 20, 30, 40, 50};

  auto source = std::make_unique<MemoryDataSource>(keys, values, 1024);
  auto scan = std::make_unique<ScanOp>(std::move(source));
  auto agg = std::make_unique<HashAggregateOp>(std::make_unique<ScanOp>(
      std::make_unique<MemoryDataSource>(keys, values, 1024)));
  auto collector = std::make_unique<ResultCollectorOp>(std::make_unique<HashAggregateOp>(
      std::make_unique<ScanOp>(std::make_unique<MemoryDataSource>(keys, values, 1024))));

  ExecContext ctx;
  ASSERT_TRUE(collector->Prepare(&ctx).ok());

  // Collect results
  std::vector<int32_t> result_keys;
  std::vector<int64_t> result_values;

  KeyValueChunk chunk;
  while (true) {
    Status status = collector->Next(&chunk);
    if (status.code() == StatusCode::kEndOfFile) {
      break;
    }
    ASSERT_TRUE(status.ok());

    if (chunk.empty()) continue;

    auto& keys_out = chunk.template GetColumn<0>();
    auto& values_out = chunk.template GetColumn<1>();

    for (size_t i = 0; i < chunk.num_rows(); ++i) {
      result_keys.push_back(keys_out.ValueAt(i));
      result_values.push_back(values_out.ValueAt(i));
    }
  }

  // Verify results
  ASSERT_EQ(result_keys.size(), 3);
  ASSERT_EQ(result_values.size(), 3);

  // Find each expected key
  bool found_1 = false, found_2 = false, found_3 = false;
  int64_t sum_1 = 0, sum_2 = 0, sum_3 = 0;

  for (size_t i = 0; i < result_keys.size(); ++i) {
    if (result_keys[i] == 1) { found_1 = true; sum_1 = result_values[i]; }
    if (result_keys[i] == 2) { found_2 = true; sum_2 = result_values[i]; }
    if (result_keys[i] == 3) { found_3 = true; sum_3 = result_values[i]; }
  }

  EXPECT_TRUE(found_1);
  EXPECT_TRUE(found_2);
  EXPECT_TRUE(found_3);
  EXPECT_EQ(sum_1, 40);  // 10 + 30
  EXPECT_EQ(sum_2, 70);  // 20 + 50
  EXPECT_EQ(sum_3, 40);
}

TEST(AggregationTest, SingleGroup) {
  // All same key: {1: 5, 1: 10, 1: 15}
  // Expected: {1: 30}
  std::vector<int32_t> keys = {1, 1, 1};
  std::vector<int64_t> values = {5, 10, 15};

  auto collector = std::make_unique<ResultCollectorOp>(std::make_unique<HashAggregateOp>(
      std::make_unique<ScanOp>(std::make_unique<MemoryDataSource>(keys, values, 1024))));

  ExecContext ctx;
  ASSERT_TRUE(collector->Prepare(&ctx).ok());

  KeyValueChunk chunk;
  std::vector<int32_t> result_keys;
  std::vector<int64_t> result_values;

  while (true) {
    Status status = collector->Next(&chunk);
    if (status.code() == StatusCode::kEndOfFile) break;
    ASSERT_TRUE(status.ok());
    if (chunk.empty()) continue;

    auto& keys_out = chunk.template GetColumn<0>();
    auto& values_out = chunk.template GetColumn<1>();

    for (size_t i = 0; i < chunk.num_rows(); ++i) {
      result_keys.push_back(keys_out.ValueAt(i));
      result_values.push_back(values_out.ValueAt(i));
    }
  }

  ASSERT_EQ(result_keys.size(), 1);
  EXPECT_EQ(result_keys[0], 1);
  EXPECT_EQ(result_values[0], 30);
}

TEST(AggregationTest, AllUniqueKeys) {
  // Each key appears once: {1: 10, 2: 20, 3: 30}
  // Note: Hash aggregation doesn't guarantee order, so we check correctness by key
  std::vector<int32_t> keys = {1, 2, 3};
  std::vector<int64_t> values = {10, 20, 30};

  auto collector = std::make_unique<ResultCollectorOp>(std::make_unique<HashAggregateOp>(
      std::make_unique<ScanOp>(std::make_unique<MemoryDataSource>(keys, values, 1024))));

  ExecContext ctx;
  ASSERT_TRUE(collector->Prepare(&ctx).ok());

  KeyValueChunk chunk;
  std::vector<int32_t> result_keys;
  std::vector<int64_t> result_values;

  while (true) {
    Status status = collector->Next(&chunk);
    if (status.code() == StatusCode::kEndOfFile) break;
    ASSERT_TRUE(status.ok());
    if (chunk.empty()) continue;

    auto& keys_out = chunk.template GetColumn<0>();
    auto& values_out = chunk.template GetColumn<1>();

    for (size_t i = 0; i < chunk.num_rows(); ++i) {
      result_keys.push_back(keys_out.ValueAt(i));
      result_values.push_back(values_out.ValueAt(i));
    }
  }

  ASSERT_EQ(result_keys.size(), 3);

  // Verify each key has the correct value (order-independent)
  for (size_t i = 0; i < result_keys.size(); ++i) {
    int32_t key = result_keys[i];
    int64_t value = result_values[i];
    if (key == 1) EXPECT_EQ(value, 10);
    else if (key == 2) EXPECT_EQ(value, 20);
    else if (key == 3) EXPECT_EQ(value, 30);
    else FAIL() << "Unexpected key: " << key;
  }
}

TEST(AggregationTest, LargeDataset) {
  // Test with larger dataset
  const size_t num_rows = 10000;
  std::vector<int32_t> keys(num_rows);
  std::vector<int64_t> values(num_rows);

  // Generate data: keys 1-1000 repeating, random values
  std::mt19937 rng(42);
  std::uniform_int_distribution<int32_t> key_dist(1, 1000);
  std::uniform_int_distribution<int64_t> value_dist(1, 100);

  for (size_t i = 0; i < num_rows; ++i) {
    keys[i] = key_dist(rng);
    values[i] = value_dist(rng);
  }

  auto collector = std::make_unique<ResultCollectorOp>(std::make_unique<HashAggregateOp>(
      std::make_unique<ScanOp>(std::make_unique<MemoryDataSource>(keys, values, 1024))));

  ExecContext ctx;
  ASSERT_TRUE(collector->Prepare(&ctx).ok());

  KeyValueChunk chunk;
  std::vector<int32_t> result_keys;
  std::vector<int64_t> result_values;

  while (true) {
    Status status = collector->Next(&chunk);
    if (status.code() == StatusCode::kEndOfFile) break;
    ASSERT_TRUE(status.ok());
    if (chunk.empty()) continue;

    auto& keys_out = chunk.template GetColumn<0>();
    auto& values_out = chunk.template GetColumn<1>();

    for (size_t i = 0; i < chunk.num_rows(); ++i) {
      result_keys.push_back(keys_out.ValueAt(i));
      result_values.push_back(values_out.ValueAt(i));
    }
  }

  // Should have 1000 unique keys
  EXPECT_EQ(result_keys.size(), 1000);
}

TEST(ScanOpTest, MemoryDataSource) {
  std::vector<int32_t> keys = {1, 2, 3, 4, 5};
  std::vector<int64_t> values = {10, 20, 30, 40, 50};

  auto source = std::make_unique<MemoryDataSource>(keys, values, 2);
  auto scan = std::make_unique<ScanOp>(std::move(source));

  ExecContext ctx;
  ASSERT_TRUE(scan->Prepare(&ctx).ok());

  // First chunk: 2 rows
  KeyValueChunk chunk1;
  Status status = scan->Next(reinterpret_cast<Chunk*>(&chunk1));
  ASSERT_TRUE(status.ok());
  EXPECT_EQ(chunk1.num_rows(), 2);

  // Second chunk: 2 rows
  KeyValueChunk chunk2;
  status = scan->Next(reinterpret_cast<Chunk*>(&chunk2));
  ASSERT_TRUE(status.ok());
  EXPECT_EQ(chunk2.num_rows(), 2);

  // Third chunk: 1 row
  KeyValueChunk chunk3;
  status = scan->Next(reinterpret_cast<Chunk*>(&chunk3));
  ASSERT_TRUE(status.ok());
  EXPECT_EQ(chunk3.num_rows(), 1);

  // EOF
  KeyValueChunk chunk4;
  status = scan->Next(reinterpret_cast<Chunk*>(&chunk4));
  EXPECT_EQ(status.code(), StatusCode::kEndOfFile);
}

}  // namespace vagg
