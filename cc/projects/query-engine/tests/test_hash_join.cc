#include <numeric>
#include <vector>

#include "gtest/gtest.h"
#include "vagg/ops/hash_join_op.h"
#include "vagg/ops/scan_op.h"
#include "vagg/ops/sink_op.h"

namespace vagg {

TEST(HashJoinTest, InnerJoinBasic) {
  // Left relation: {key, value}
  // Right relation: {key, value}
  // Join on key
  std::vector<int32_t> left_keys = {1, 2, 3, 4, 5};
  std::vector<int64_t> left_values = {10, 20, 30, 40, 50};

  std::vector<int32_t> right_keys = {3, 4, 5, 6, 7};
  std::vector<int64_t> right_values = {300, 400, 500, 600, 700};

  // Expected: (3, 30, 300), (4, 40, 400), (5, 50, 500)
  auto left_source = std::make_unique<MemoryDataSource>(left_keys, left_values, 1024);
  auto right_source = std::make_unique<MemoryDataSource>(right_keys, right_values, 1024);

  auto left_scan = std::make_unique<ScanOp>(std::move(left_source));
  auto right_scan = std::make_unique<ScanOp>(std::move(right_source));

  auto join = std::make_unique<HashJoinOp>(
      std::move(left_scan),
      std::move(right_scan),
      JoinType::kInner);

  ExecContext ctx;
  ASSERT_TRUE(join->Prepare(&ctx).ok());

  std::vector<int32_t> result_keys;
  std::vector<int64_t> result_left_values;
  std::vector<int64_t> result_right_values;

  JoinOutputChunk chunk;
  while (true) {
    Status status = join->Next(&chunk);
    if (status.code() == StatusCode::kEndOfFile) break;
    ASSERT_TRUE(status.ok());

    if (chunk.empty()) continue;

    for (size_t i = 0; i < chunk.num_rows(); ++i) {
      result_keys.push_back(chunk.GetColumn<0>().ValueAt(i));
      result_left_values.push_back(chunk.GetColumn<1>().ValueAt(i));
      result_right_values.push_back(chunk.GetColumn<2>().ValueAt(i));
    }
  }

  // Should have 3 matching rows
  EXPECT_EQ(result_keys.size(), 3);
  EXPECT_EQ(result_keys[0], 3);
  EXPECT_EQ(result_keys[1], 4);
  EXPECT_EQ(result_keys[2], 5);

  // Verify values
  EXPECT_EQ(result_left_values[0], 30);
  EXPECT_EQ(result_left_values[1], 40);
  EXPECT_EQ(result_left_values[2], 50);

  EXPECT_EQ(result_right_values[0], 300);
  EXPECT_EQ(result_right_values[1], 400);
  EXPECT_EQ(result_right_values[2], 500);
}

TEST(HashJoinTest, LeftJoinBasic) {
  // LEFT JOIN is not fully implemented yet - it requires tracking unmatched build keys
  // For now, skip this test
  GTEST_SKIP() << "LEFT JOIN requires tracking unmatched build keys - not yet implemented";
}

TEST(HashJoinTest, NoMatches) {
  // No matching keys
  std::vector<int32_t> left_keys = {1, 2, 3};
  std::vector<int64_t> left_values = {10, 20, 30};

  std::vector<int32_t> right_keys = {4, 5, 6};
  std::vector<int64_t> right_values = {400, 500, 600};

  auto left_scan = std::make_unique<ScanOp>(
      std::make_unique<MemoryDataSource>(left_keys, left_values, 1024));
  auto right_scan = std::make_unique<ScanOp>(
      std::make_unique<MemoryDataSource>(right_keys, right_values, 1024));

  auto join = std::make_unique<HashJoinOp>(
      std::move(left_scan),
      std::move(right_scan),
      JoinType::kInner);

  ExecContext ctx;
  ASSERT_TRUE(join->Prepare(&ctx).ok());

  size_t total_rows = 0;
  JoinOutputChunk chunk;
  while (true) {
    Status status = join->Next(&chunk);
    if (status.code() == StatusCode::kEndOfFile) break;
    ASSERT_TRUE(status.ok());
    total_rows += chunk.num_rows();
  }

  // Inner join with no matches = empty result
  EXPECT_EQ(total_rows, 0);
}

TEST(HashJoinTest, AllMatch) {
  // All keys match
  std::vector<int32_t> left_keys = {1, 2, 3};
  std::vector<int64_t> left_values = {10, 20, 30};

  std::vector<int32_t> right_keys = {1, 2, 3};
  std::vector<int64_t> right_values = {100, 200, 300};

  auto left_scan = std::make_unique<ScanOp>(
      std::make_unique<MemoryDataSource>(left_keys, left_values, 1024));
  auto right_scan = std::make_unique<ScanOp>(
      std::make_unique<MemoryDataSource>(right_keys, right_values, 1024));

  auto join = std::make_unique<HashJoinOp>(
      std::move(left_scan),
      std::move(right_scan),
      JoinType::kInner);

  ExecContext ctx;
  ASSERT_TRUE(join->Prepare(&ctx).ok());

  std::vector<int32_t> result_keys;
  JoinOutputChunk chunk;
  while (true) {
    Status status = join->Next(&chunk);
    if (status.code() == StatusCode::kEndOfFile) break;
    ASSERT_TRUE(status.ok());

    for (size_t i = 0; i < chunk.num_rows(); ++i) {
      result_keys.push_back(chunk.GetColumn<0>().ValueAt(i));
    }
  }

  // All 3 rows should match
  EXPECT_EQ(result_keys.size(), 3);
  EXPECT_EQ(result_keys[0], 1);
  EXPECT_EQ(result_keys[1], 2);
  EXPECT_EQ(result_keys[2], 3);
}

TEST(HashJoinTest, LargeDataset) {
  // Test with larger dataset
  const size_t num_left = 10000;
  const size_t num_right = 10000;
  const int32_t key_range = 1000;

  std::vector<int32_t> left_keys(num_left);
  std::vector<int64_t> left_values(num_left);
  std::mt19937 rng(42);
  std::uniform_int_distribution<int32_t> key_dist(1, key_range);
  std::uniform_int_distribution<int64_t> value_dist(1, 1000);

  for (size_t i = 0; i < num_left; ++i) {
    left_keys[i] = key_dist(rng);
    left_values[i] = value_dist(rng);
  }

  std::vector<int32_t> right_keys(num_right);
  std::vector<int64_t> right_values(num_right);

  for (size_t i = 0; i < num_right; ++i) {
    right_keys[i] = key_dist(rng);
    right_values[i] = value_dist(rng);
  }

  auto left_scan = std::make_unique<ScanOp>(
      std::make_unique<MemoryDataSource>(left_keys, left_values, 4096));
  auto right_scan = std::make_unique<ScanOp>(
      std::make_unique<MemoryDataSource>(right_keys, right_values, 4096));

  auto join = std::make_unique<HashJoinOp>(
      std::move(left_scan),
      std::move(right_scan),
      JoinType::kInner);

  ExecContext ctx;
  ASSERT_TRUE(join->Prepare(&ctx).ok());

  // Get stats after Prepare (build phase is done)
  auto stats_before = join->GetStats();
  EXPECT_EQ(stats_before.build_rows, num_left);
  // probe_rows is 0 at this point

  // Now run the probe phase
  size_t total_rows = 0;
  JoinOutputChunk chunk;
  while (true) {
    Status status = join->Next(&chunk);
    if (status.code() == StatusCode::kEndOfFile) break;
    ASSERT_TRUE(status.ok());
    total_rows += chunk.num_rows();
  }

  // Check final stats
  auto stats = join->GetStats();
  EXPECT_EQ(stats.build_rows, num_left);
  EXPECT_EQ(stats.probe_rows, num_right);
}

TEST(NestedLoopJoinTest, Basic) {
  // Small dataset for nested loop join
  std::vector<int32_t> left_keys = {1, 2, 3};
  std::vector<int64_t> left_values = {10, 20, 30};

  std::vector<int32_t> right_keys = {2, 3, 4};
  std::vector<int64_t> right_values = {200, 300, 400};

  auto left_scan = std::make_unique<ScanOp>(
      std::make_unique<MemoryDataSource>(left_keys, left_values, 1024));
  auto right_scan = std::make_unique<ScanOp>(
      std::make_unique<MemoryDataSource>(right_keys, right_values, 1024));

  auto join = std::make_unique<NestedLoopJoinOp>(
      std::move(left_scan),
      std::move(right_scan));

  ExecContext ctx;
  ASSERT_TRUE(join->Prepare(&ctx).ok());

  std::vector<int32_t> result_keys;
  JoinOutputChunk chunk;
  while (true) {
    Status status = join->Next(&chunk);
    if (status.code() == StatusCode::kEndOfFile) break;
    ASSERT_TRUE(status.ok());

    for (size_t i = 0; i < chunk.num_rows(); ++i) {
      result_keys.push_back(chunk.GetColumn<0>().ValueAt(i));
    }
  }

  // Should match: (2, 20, 200), (3, 30, 300)
  EXPECT_EQ(result_keys.size(), 2);
  EXPECT_EQ(result_keys[0], 2);
  EXPECT_EQ(result_keys[1], 3);
}

}  // namespace vagg
