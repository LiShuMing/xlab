#ifndef VAGG_VECTOR_CHUNK_H_
#define VAGG_VECTOR_CHUNK_H_

#include <cstddef>
#include <memory>
#include <tuple>
#include <vector>

#include "vagg/vector/types.h"
#include "vagg/vector/vector.h"

namespace vagg {

// Forward declare
template <typename... Types>
class TypedChunk;

// Base chunk class (polymorphic interface)
class Chunk {
 public:
  Chunk() : num_rows_(0), num_columns_(0) {}
  virtual ~Chunk() = default;

  size_t num_rows() const { return num_rows_; }
  size_t num_columns() const { return num_columns_; }
  bool empty() const { return num_rows_ == 0; }

  void SetNumRows(size_t n) { num_rows_ = n; }

  // Virtual clone for creating typed copies
  virtual Chunk* Clone() const = 0;

 protected:
  size_t num_rows_ = 0;
  size_t num_columns_ = 0;
};

// Simple chunk implementation with typed columns
template <typename... Types>
class TypedChunk : public Chunk {
 public:
  TypedChunk() { num_columns_ = sizeof...(Types); }

  Chunk* Clone() const override {
    auto* copy = new TypedChunk<Types...>();
    copy->num_rows_ = num_rows_;
    copy->num_columns_ = num_columns_;
    copy->columns_ = columns_;
    return copy;
  }

  template <size_t I>
  auto& GetColumn() {
    return std::get<I>(columns_);
  }

  template <size_t I>
  const auto& GetColumn() const {
    return std::get<I>(columns_);
  }

 private:
  std::tuple<FlatVector<Types>...> columns_;
};

// Chunk with 2 columns: int32 key, int64 value (for our target query)
using KeyValueChunk = TypedChunk<int32_t, int64_t>;

// Chunk with 3 columns: used for join output (key, left_value, right_value)
using JoinOutputChunk = TypedChunk<int32_t, int64_t, int64_t>;

// Helper to create KeyValueChunk with pre-allocated capacity
inline KeyValueChunk MakeKeyValueChunk(size_t capacity) {
  KeyValueChunk chunk;
  chunk.GetColumn<0>().Resize(capacity);
  chunk.GetColumn<1>().Resize(capacity);
  return chunk;
}

// Helper to create JoinOutputChunk with pre-allocated capacity
inline JoinOutputChunk MakeJoinOutputChunk(size_t capacity) {
  JoinOutputChunk chunk;
  chunk.GetColumn<0>().Resize(capacity);  // Join key
  chunk.GetColumn<1>().Resize(capacity);  // Left value
  chunk.GetColumn<2>().Resize(capacity);  // Right value
  return chunk;
}

}  // namespace vagg

#endif  // VAGG_VECTOR_CHUNK_H_
