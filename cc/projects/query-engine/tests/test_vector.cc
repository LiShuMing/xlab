#include <numeric>

#include "gtest/gtest.h"
#include "vagg/vector/chunk.h"
#include "vagg/vector/selection.h"
#include "vagg/vector/types.h"
#include "vagg/vector/vector.h"

namespace vagg {

TEST(VectorTest, FlatVectorInt32) {
  FlatVector<int32_t> vec(10);

  // Write some values
  for (int32_t i = 0; i < 10; ++i) {
    vec.ValueAt(i) = i * 2;
  }

  // Verify
  for (int32_t i = 0; i < 10; ++i) {
    EXPECT_EQ(vec.ValueAt(i), i * 2);
  }

  EXPECT_EQ(vec.size(), 10);
}

TEST(VectorTest, FlatVectorInt64) {
  FlatVector<int64_t> vec(5);

  for (size_t i = 0; i < 5; ++i) {
    vec.ValueAt(i) = static_cast<int64_t>(i) * 1000000000LL;
  }

  EXPECT_EQ(vec.ValueAt(0), 0);
  EXPECT_EQ(vec.ValueAt(4), 4000000000LL);
}

TEST(VectorTest, ValidityBitmap) {
  ValidityBitmap bitmap(100, true);

  // All should be valid
  for (size_t i = 0; i < 100; ++i) {
    EXPECT_TRUE(bitmap.IsValid(i));
  }

  // Set some to null
  bitmap.SetValid(10, false);
  bitmap.SetValid(50, false);
  bitmap.SetValid(99, false);

  EXPECT_FALSE(bitmap.IsValid(10));
  EXPECT_FALSE(bitmap.IsValid(50));
  EXPECT_FALSE(bitmap.IsValid(99));
  EXPECT_TRUE(bitmap.IsValid(11));  // Unchanged

  // Toggle back
  bitmap.SetValid(10, true);
  EXPECT_TRUE(bitmap.IsValid(10));
}

TEST(VectorTest, ValidityBitmapEdgeCases) {
  // Test with non-power-of-2 size
  ValidityBitmap bitmap(70, true);

  EXPECT_EQ(bitmap.num_bits(), 70);
  EXPECT_EQ(bitmap.num_words(), 2);  // 70 / 64 = 1.something

  // Last bit should be valid
  EXPECT_TRUE(bitmap.IsValid(69));
}

TEST(VectorTest, SelectionVector) {
  SelectionVector sel(10);

  // Fill with indices using operator[]
  for (size_t i = 0; i < 10; ++i) {
    sel[i] = static_cast<uint32_t>(i * 2);
  }

  EXPECT_EQ(sel[0], 0);
  EXPECT_EQ(sel[9], 18);

  // Append adds a new element - note: size starts at 0, so Append adds at index 0
  sel.Append(100);
  EXPECT_EQ(sel[0], 100);  // Append overwrites since size is still 0
  EXPECT_EQ(sel.size(), 1);

  // Test appending multiple elements
  sel.Append(200);
  sel.Append(300);
  EXPECT_EQ(sel.size(), 3);
  EXPECT_EQ(sel[0], 100);
  EXPECT_EQ(sel[1], 200);
  EXPECT_EQ(sel[2], 300);
}

TEST(VectorTest, KeyValueChunk) {
  auto chunk = MakeKeyValueChunk(100);

  auto& keys = chunk.template GetColumn<0>();
  auto& values = chunk.template GetColumn<1>();

  // Fill with data
  for (size_t i = 0; i < 100; ++i) {
    keys.ValueAt(i) = static_cast<int32_t>(i);
    values.ValueAt(i) = static_cast<int64_t>(i) * 10;
  }

  chunk.SetNumRows(100);

  EXPECT_EQ(chunk.num_rows(), 100);
  EXPECT_EQ(keys.ValueAt(50), 50);
  EXPECT_EQ(values.ValueAt(50), 500);
}

TEST(VectorTest, KeyValueChunkMultipleBatches) {
  // Simulate processing multiple batches
  auto chunk1 = MakeKeyValueChunk(10);
  auto& keys1 = chunk1.template GetColumn<0>();
  auto& values1 = chunk1.template GetColumn<1>();

  for (size_t i = 0; i < 10; ++i) {
    keys1.ValueAt(i) = static_cast<int32_t>(i);
    values1.ValueAt(i) = static_cast<int64_t>(i);
  }
  chunk1.SetNumRows(10);

  auto chunk2 = MakeKeyValueChunk(10);
  auto& keys2 = chunk2.template GetColumn<0>();
  auto& values2 = chunk2.template GetColumn<1>();

  for (size_t i = 0; i < 5; ++i) {
    keys2.ValueAt(i) = static_cast<int32_t>(10 + i);
    values2.ValueAt(i) = static_cast<int64_t>(10 + i);
  }
  chunk2.SetNumRows(5);

  // Verify first batch
  EXPECT_EQ(chunk1.num_rows(), 10);
  EXPECT_EQ(keys1.ValueAt(0), 0);
  EXPECT_EQ(keys1.ValueAt(9), 9);

  // Verify second batch
  EXPECT_EQ(chunk2.num_rows(), 5);
  EXPECT_EQ(keys2.ValueAt(0), 10);
  EXPECT_EQ(keys2.ValueAt(4), 14);
}

TEST(VectorTest, TypeSystem) {
  EXPECT_EQ(TypeSize(TypeKind::kInt32), sizeof(int32_t));
  EXPECT_EQ(TypeSize(TypeKind::kInt64), sizeof(int64_t));
  EXPECT_EQ(TypeSize(TypeKind::kFloat64), sizeof(double));

  EXPECT_EQ(TypeKindFromString("INT32"), TypeKind::kInt32);
  EXPECT_EQ(TypeKindFromString("int64"), TypeKind::kInt64);
  EXPECT_EQ(TypeKindFromString("UNKNOWN"), TypeKind::kUnknown);
}

TEST(VectorTest, Schema) {
  Schema schema = Schema::FromTypes({
      Type::Int32(),
      Type::Int64(),
      Type::Float64()
  });

  EXPECT_EQ(schema.num_columns(), 3);
  EXPECT_EQ(schema.kind(0), TypeKind::kInt32);
  EXPECT_EQ(schema.kind(1), TypeKind::kInt64);
  EXPECT_EQ(schema.kind(2), TypeKind::kFloat64);
}

}  // namespace vagg
