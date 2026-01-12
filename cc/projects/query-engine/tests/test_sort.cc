#include <algorithm>
#include <random>
#include <vector>

#include "gtest/gtest.h"
#include "vagg/ops/scan_op.h"
#include "vagg/ops/sort_op.h"

namespace vagg {

TEST(SortOpTest, AscendingSort) {
  // Unsorted input
  std::vector<int32_t> keys = {5, 2, 8, 1, 9, 3, 7, 4, 6};
  std::vector<int64_t> values = {50, 20, 80, 10, 90, 30, 70, 40, 60};

  auto scan = std::make_unique<ScanOp>(
      std::make_unique<MemoryDataSource>(keys, values, 1024));

  auto sort = std::make_unique<SortOp>(std::move(scan), 0, SortDirection::kAscending);

  ExecContext ctx;
  ASSERT_TRUE(sort->Prepare(&ctx).ok());

  // Collect sorted output
  std::vector<int32_t> result_keys;
  std::vector<int64_t> result_values;
  KeyValueChunk chunk;

  while (true) {
    Status status = sort->Next(&chunk);
    if (status.code() == StatusCode::kEndOfFile) break;
    ASSERT_TRUE(status.ok());

    for (size_t i = 0; i < chunk.num_rows(); ++i) {
      result_keys.push_back(chunk.GetColumn<0>().ValueAt(i));
      result_values.push_back(chunk.GetColumn<1>().ValueAt(i));
    }
  }

  // Verify sorted order
  ASSERT_EQ(result_keys.size(), 9);
  EXPECT_EQ(result_keys[0], 1);
  EXPECT_EQ(result_keys[1], 2);
  EXPECT_EQ(result_keys[2], 3);
  EXPECT_EQ(result_keys[3], 4);
  EXPECT_EQ(result_keys[4], 5);
  EXPECT_EQ(result_keys[5], 6);
  EXPECT_EQ(result_keys[6], 7);
  EXPECT_EQ(result_keys[7], 8);
  EXPECT_EQ(result_keys[8], 9);

  // Verify values followed keys
  EXPECT_EQ(result_values[0], 10);
  EXPECT_EQ(result_values[1], 20);
  EXPECT_EQ(result_values[2], 30);
}

TEST(SortOpTest, DescendingSort) {
  std::vector<int32_t> keys = {5, 2, 8, 1, 9, 3, 7, 4, 6};
  std::vector<int64_t> values = {50, 20, 80, 10, 90, 30, 70, 40, 60};

  auto scan = std::make_unique<ScanOp>(
      std::make_unique<MemoryDataSource>(keys, values, 1024));

  auto sort = std::make_unique<SortOp>(std::move(scan), 0, SortDirection::kDescending);

  ExecContext ctx;
  ASSERT_TRUE(sort->Prepare(&ctx).ok());

  std::vector<int32_t> result_keys;
  KeyValueChunk chunk;

  while (true) {
    Status status = sort->Next(&chunk);
    if (status.code() == StatusCode::kEndOfFile) break;
    ASSERT_TRUE(status.ok());

    for (size_t i = 0; i < chunk.num_rows(); ++i) {
      result_keys.push_back(chunk.GetColumn<0>().ValueAt(i));
    }
  }

  ASSERT_EQ(result_keys.size(), 9);
  EXPECT_EQ(result_keys[0], 9);
  EXPECT_EQ(result_keys[1], 8);
  EXPECT_EQ(result_keys[2], 7);
  EXPECT_EQ(result_keys[3], 6);
  EXPECT_EQ(result_keys[4], 5);
  EXPECT_EQ(result_keys[5], 4);
  EXPECT_EQ(result_keys[6], 3);
  EXPECT_EQ(result_keys[7], 2);
  EXPECT_EQ(result_keys[8], 1);
}

TEST(SortOpTest, NegativeNumbers) {
  std::vector<int32_t> keys = {-5, 2, -8, 1, 9, -3, 7, -4, 6};
  std::vector<int64_t> values = {1, 2, 3, 4, 5, 6, 7, 8, 9};

  auto scan = std::make_unique<ScanOp>(
      std::make_unique<MemoryDataSource>(keys, values, 1024));

  auto sort = std::make_unique<SortOp>(std::move(scan), 0, SortDirection::kAscending);

  ExecContext ctx;
  ASSERT_TRUE(sort->Prepare(&ctx).ok());

  std::vector<int32_t> result_keys;
  KeyValueChunk chunk;

  while (true) {
    Status status = sort->Next(&chunk);
    if (status.code() == StatusCode::kEndOfFile) break;
    ASSERT_TRUE(status.ok());

    for (size_t i = 0; i < chunk.num_rows(); ++i) {
      result_keys.push_back(chunk.GetColumn<0>().ValueAt(i));
    }
  }

  ASSERT_EQ(result_keys.size(), 9);
  EXPECT_EQ(result_keys[0], -8);
  EXPECT_EQ(result_keys[1], -5);
  EXPECT_EQ(result_keys[2], -4);
  EXPECT_EQ(result_keys[3], -3);
  EXPECT_EQ(result_keys[4], 1);
  EXPECT_EQ(result_keys[5], 2);
  EXPECT_EQ(result_keys[6], 6);
  EXPECT_EQ(result_keys[7], 7);
  EXPECT_EQ(result_keys[8], 9);
}

TEST(SortOpTest, EmptyInput) {
  std::vector<int32_t> keys;
  std::vector<int64_t> values;

  auto scan = std::make_unique<ScanOp>(
      std::make_unique<MemoryDataSource>(keys, values, 1024));

  auto sort = std::make_unique<SortOp>(std::move(scan), 0, SortDirection::kAscending);

  ExecContext ctx;
  ASSERT_TRUE(sort->Prepare(&ctx).ok());

  KeyValueChunk chunk;
  Status status = sort->Next(&chunk);
  EXPECT_EQ(status.code(), StatusCode::kEndOfFile);
}

TEST(SortOpTest, SingleElement) {
  std::vector<int32_t> keys = {42};
  std::vector<int64_t> values = {100};

  auto scan = std::make_unique<ScanOp>(
      std::make_unique<MemoryDataSource>(keys, values, 1024));

  auto sort = std::make_unique<SortOp>(std::move(scan), 0, SortDirection::kAscending);

  ExecContext ctx;
  ASSERT_TRUE(sort->Prepare(&ctx).ok());

  KeyValueChunk chunk;
  Status status = sort->Next(&chunk);
  ASSERT_TRUE(status.ok());
  EXPECT_EQ(chunk.num_rows(), 1);
  EXPECT_EQ(chunk.GetColumn<0>().ValueAt(0), 42);
  EXPECT_EQ(chunk.GetColumn<1>().ValueAt(0), 100);
}

TEST(SortOpTest, LargeDataset) {
  const size_t num_rows = 50000;
  std::vector<int32_t> keys(num_rows);
  std::vector<int64_t> values(num_rows);

  std::mt19937 rng(42);
  std::uniform_int_distribution<int32_t> key_dist(-1000000, 1000000);
  std::uniform_int_distribution<int64_t> value_dist(1, 1000000);

  for (size_t i = 0; i < num_rows; ++i) {
    keys[i] = key_dist(rng);
    values[i] = value_dist(rng);
  }

  // Shuffle to create unsorted input
  std::shuffle(keys.begin(), keys.end(), rng);
  for (size_t i = 0; i < num_rows; ++i) {
    values[i] = static_cast<int64_t>(keys[i]) * 1000;  // Value derived from key
  }

  auto scan = std::make_unique<ScanOp>(
      std::make_unique<MemoryDataSource>(keys, values, 4096));

  auto sort = std::make_unique<SortOp>(std::move(scan), 0, SortDirection::kAscending);

  ExecContext ctx;
  ASSERT_TRUE(sort->Prepare(&ctx).ok());

  std::vector<int32_t> result_keys;
  std::vector<int64_t> result_values;
  KeyValueChunk chunk;

  while (true) {
    Status status = sort->Next(&chunk);
    if (status.code() == StatusCode::kEndOfFile) break;
    ASSERT_TRUE(status.ok());

    for (size_t i = 0; i < chunk.num_rows(); ++i) {
      result_keys.push_back(chunk.GetColumn<0>().ValueAt(i));
      result_values.push_back(chunk.GetColumn<1>().ValueAt(i));
    }
  }

  ASSERT_EQ(result_keys.size(), num_rows);

  // Verify sorted order
  for (size_t i = 1; i < result_keys.size(); ++i) {
    EXPECT_GE(result_keys[i], result_keys[i - 1])
        << "Sort order violated at index " << i;
  }

  // Verify stability (values should match keys * 1000)
  for (size_t i = 0; i < result_keys.size(); ++i) {
    EXPECT_EQ(result_values[i], static_cast<int64_t>(result_keys[i]) * 1000);
  }
}

TEST(SortOpTest, AlreadySorted) {
  std::vector<int32_t> keys = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10};
  std::vector<int64_t> values = {10, 20, 30, 40, 50, 60, 70, 80, 90, 100};

  auto scan = std::make_unique<ScanOp>(
      std::make_unique<MemoryDataSource>(keys, values, 1024));

  auto sort = std::make_unique<SortOp>(std::move(scan), 0, SortDirection::kAscending);

  ExecContext ctx;
  ASSERT_TRUE(sort->Prepare(&ctx).ok());

  std::vector<int32_t> result_keys;
  KeyValueChunk chunk;

  while (true) {
    Status status = sort->Next(&chunk);
    if (status.code() == StatusCode::kEndOfFile) break;
    ASSERT_TRUE(status.ok());

    for (size_t i = 0; i < chunk.num_rows(); ++i) {
      result_keys.push_back(chunk.GetColumn<0>().ValueAt(i));
    }
  }

  ASSERT_EQ(result_keys.size(), 10);
  EXPECT_EQ(result_keys, keys);  // Should be unchanged
}

TEST(SortOpTest, Duplicates) {
  std::vector<int32_t> keys = {5, 2, 5, 1, 2, 3, 2, 4, 5};
  std::vector<int64_t> values = {1, 2, 3, 4, 5, 6, 7, 8, 9};

  auto scan = std::make_unique<ScanOp>(
      std::make_unique<MemoryDataSource>(keys, values, 1024));

  auto sort = std::make_unique<SortOp>(std::move(scan), 0, SortDirection::kAscending);

  ExecContext ctx;
  ASSERT_TRUE(sort->Prepare(&ctx).ok());

  std::vector<int32_t> result_keys;
  KeyValueChunk chunk;

  while (true) {
    Status status = sort->Next(&chunk);
    if (status.code() == StatusCode::kEndOfFile) break;
    ASSERT_TRUE(status.ok());

    for (size_t i = 0; i < chunk.num_rows(); ++i) {
      result_keys.push_back(chunk.GetColumn<0>().ValueAt(i));
    }
  }

  ASSERT_EQ(result_keys.size(), 9);
  EXPECT_EQ(result_keys[0], 1);
  EXPECT_EQ(result_keys[1], 2);
  EXPECT_EQ(result_keys[2], 2);
  EXPECT_EQ(result_keys[3], 2);
  EXPECT_EQ(result_keys[4], 3);
  EXPECT_EQ(result_keys[5], 4);
  EXPECT_EQ(result_keys[6], 5);
  EXPECT_EQ(result_keys[7], 5);
  EXPECT_EQ(result_keys[8], 5);
}

TEST(TopNOpTest, Top5Smallest) {
  std::vector<int32_t> keys = {5, 2, 8, 1, 9, 3, 7, 4, 6};
  std::vector<int64_t> values = {50, 20, 80, 10, 90, 30, 70, 40, 60};

  auto scan = std::make_unique<ScanOp>(
      std::make_unique<MemoryDataSource>(keys, values, 1024));

  auto topn = std::make_unique<TopNOp>(std::move(scan), 5, 0, SortDirection::kAscending);

  ExecContext ctx;
  ASSERT_TRUE(topn->Prepare(&ctx).ok());

  std::vector<int32_t> result_keys;
  std::vector<int64_t> result_values;
  KeyValueChunk chunk;

  while (true) {
    Status status = topn->Next(&chunk);
    if (status.code() == StatusCode::kEndOfFile) break;
    ASSERT_TRUE(status.ok());

    for (size_t i = 0; i < chunk.num_rows(); ++i) {
      result_keys.push_back(chunk.GetColumn<0>().ValueAt(i));
      result_values.push_back(chunk.GetColumn<1>().ValueAt(i));
    }
  }

  ASSERT_EQ(result_keys.size(), 5);
  EXPECT_EQ(result_keys[0], 1);
  EXPECT_EQ(result_keys[1], 2);
  EXPECT_EQ(result_keys[2], 3);
  EXPECT_EQ(result_keys[3], 4);
  EXPECT_EQ(result_keys[4], 5);
}

TEST(TopNOpTest, Top5Largest) {
  std::vector<int32_t> keys = {5, 2, 8, 1, 9, 3, 7, 4, 6};
  std::vector<int64_t> values = {50, 20, 80, 10, 90, 30, 70, 40, 60};

  auto scan = std::make_unique<ScanOp>(
      std::make_unique<MemoryDataSource>(keys, values, 1024));

  auto topn = std::make_unique<TopNOp>(std::move(scan), 5, 0, SortDirection::kDescending);

  ExecContext ctx;
  ASSERT_TRUE(topn->Prepare(&ctx).ok());

  std::vector<int32_t> result_keys;
  KeyValueChunk chunk;

  while (true) {
    Status status = topn->Next(&chunk);
    if (status.code() == StatusCode::kEndOfFile) break;
    ASSERT_TRUE(status.ok());

    for (size_t i = 0; i < chunk.num_rows(); ++i) {
      result_keys.push_back(chunk.GetColumn<0>().ValueAt(i));
    }
  }

  ASSERT_EQ(result_keys.size(), 5);
  EXPECT_EQ(result_keys[0], 9);
  EXPECT_EQ(result_keys[1], 8);
  EXPECT_EQ(result_keys[2], 7);
  EXPECT_EQ(result_keys[3], 6);
  EXPECT_EQ(result_keys[4], 5);
}

TEST(TopNOpTest, TopNWithNegativeNumbers) {
  std::vector<int32_t> keys = {-5, 2, -8, 1, 9, -3, 7, -4, 6};
  std::vector<int64_t> values = {1, 2, 3, 4, 5, 6, 7, 8, 9};

  auto scan = std::make_unique<ScanOp>(
      std::make_unique<MemoryDataSource>(keys, values, 1024));

  auto topn = std::make_unique<TopNOp>(std::move(scan), 3, 0, SortDirection::kAscending);

  ExecContext ctx;
  ASSERT_TRUE(topn->Prepare(&ctx).ok());

  std::vector<int32_t> result_keys;
  KeyValueChunk chunk;

  while (true) {
    Status status = topn->Next(&chunk);
    if (status.code() == StatusCode::kEndOfFile) break;
    ASSERT_TRUE(status.ok());

    for (size_t i = 0; i < chunk.num_rows(); ++i) {
      result_keys.push_back(chunk.GetColumn<0>().ValueAt(i));
    }
  }

  ASSERT_EQ(result_keys.size(), 3);
  EXPECT_EQ(result_keys[0], -8);
  EXPECT_EQ(result_keys[1], -5);
  EXPECT_EQ(result_keys[2], -4);
}

TEST(TopNOpTest, NExceedsInputSize) {
  std::vector<int32_t> keys = {5, 2, 8};
  std::vector<int64_t> values = {50, 20, 80};

  auto scan = std::make_unique<ScanOp>(
      std::make_unique<MemoryDataSource>(keys, values, 1024));

  auto topn = std::make_unique<TopNOp>(std::move(scan), 100, 0, SortDirection::kAscending);

  ExecContext ctx;
  ASSERT_TRUE(topn->Prepare(&ctx).ok());

  std::vector<int32_t> result_keys;
  KeyValueChunk chunk;

  while (true) {
    Status status = topn->Next(&chunk);
    if (status.code() == StatusCode::kEndOfFile) break;
    ASSERT_TRUE(status.ok());

    for (size_t i = 0; i < chunk.num_rows(); ++i) {
      result_keys.push_back(chunk.GetColumn<0>().ValueAt(i));
    }
  }

  ASSERT_EQ(result_keys.size(), 3);
  EXPECT_EQ(result_keys[0], 2);
  EXPECT_EQ(result_keys[1], 5);
  EXPECT_EQ(result_keys[2], 8);
}

TEST(TopNOpTest, LargeDataset) {
  const size_t num_rows = 100000;
  const size_t n = 100;

  std::vector<int32_t> keys(num_rows);
  std::vector<int64_t> values(num_rows);

  std::mt19937 rng(42);
  std::uniform_int_distribution<int32_t> key_dist(1, 1000000);

  for (size_t i = 0; i < num_rows; ++i) {
    keys[i] = key_dist(rng);
    values[i] = keys[i] * 10;
  }

  auto scan = std::make_unique<ScanOp>(
      std::make_unique<MemoryDataSource>(keys, values, 4096));

  auto topn = std::make_unique<TopNOp>(std::move(scan), n, 0, SortDirection::kAscending);

  ExecContext ctx;
  ASSERT_TRUE(topn->Prepare(&ctx).ok());

  std::vector<int32_t> result_keys;
  KeyValueChunk chunk;

  while (true) {
    Status status = topn->Next(&chunk);
    if (status.code() == StatusCode::kEndOfFile) break;
    ASSERT_TRUE(status.ok());

    for (size_t i = 0; i < chunk.num_rows(); ++i) {
      result_keys.push_back(chunk.GetColumn<0>().ValueAt(i));
    }
  }

  ASSERT_EQ(result_keys.size(), n);

  // Verify sorted order
  for (size_t i = 1; i < result_keys.size(); ++i) {
    EXPECT_GE(result_keys[i], result_keys[i - 1]);
  }

  // Verify these are indeed the smallest n values
  std::vector<int32_t> sorted_input = keys;
  std::sort(sorted_input.begin(), sorted_input.end());
  for (size_t i = 0; i < n; ++i) {
    EXPECT_EQ(result_keys[i], sorted_input[i]);
  }
}

}  // namespace vagg
