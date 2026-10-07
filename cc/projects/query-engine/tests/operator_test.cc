#include <gtest/gtest.h>

#include <map>
#include <memory>
#include <vector>

#include "vagg/ht/hash_table.h"
#include "vagg/ops/aggregate_op.h"
#include "vagg/ops/scan_op.h"

TEST(QueryEngineTest, HashTableRetainsEntriesAfterGrowth) {
    vagg::Int32Int64HashTable table;
    for (int32_t key = 0; key < 10000; ++key) {
        table.FindOrInsert(key)->value += key * 3;
    }
    for (int32_t key = 0; key < 10000; ++key) {
        ASSERT_NE(table.Find(key), nullptr);
        EXPECT_EQ(table.Find(key)->value, key * 3);
    }
    EXPECT_EQ(table.Find(-1), nullptr);
}

TEST(QueryEngineTest, AggregationCombinesGroupsAcrossBatches) {
    auto source = std::make_unique<vagg::MemoryDataSource>(
            std::vector<int32_t> {2, 1, 2, 3, 1}, std::vector<int64_t> {10, 20, 30, 40, 50}, 2);
    vagg::HashAggregateOp aggregate(std::make_unique<vagg::ScanOp>(std::move(source)), 0, 1);
    ASSERT_TRUE(aggregate.Prepare(nullptr).ok());
    std::map<int32_t, int64_t> results;
    vagg::KeyValueChunk chunk;
    while (true) {
        auto status = aggregate.Next(&chunk);
        if (status.code() == vagg::StatusCode::kEndOfFile) {
            break;
        }
        ASSERT_TRUE(status.ok());
        for (size_t row = 0; row < chunk.num_rows(); ++row) {
            results.emplace(chunk.GetColumn<0>().ValueAt(row), chunk.GetColumn<1>().ValueAt(row));
        }
    }
    const std::map<int32_t, int64_t> expected {{1, 70}, {2, 40}, {3, 40}};
    EXPECT_EQ(results, expected);
}

TEST(QueryEngineTest, EmptyInputFinishesWithoutRows) {
    auto source = std::make_unique<vagg::MemoryDataSource>(std::vector<int32_t> {},
                                                           std::vector<int64_t> {});
    vagg::HashAggregateOp aggregate(std::make_unique<vagg::ScanOp>(std::move(source)), 0, 1);
    ASSERT_TRUE(aggregate.Prepare(nullptr).ok());
    vagg::KeyValueChunk chunk;
    EXPECT_EQ(aggregate.Next(&chunk).code(), vagg::StatusCode::kEndOfFile);
}
