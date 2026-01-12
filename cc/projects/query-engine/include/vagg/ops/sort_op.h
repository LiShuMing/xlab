#ifndef VAGG_OPS_SORT_OP_H_
#define VAGG_OPS_SORT_OP_H_

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <vector>

#include "vagg/exec/operator.h"
#include "vagg/vector/chunk.h"
#include "vagg/vector/vector.h"

namespace vagg {

// Sort direction for ordering
enum class SortDirection {
  kAscending,
  kDescending
};

// Sort nulls handling
enum class NullsOrder {
  kFirst,   // NULLs come first
  kLast     // NULLs come last
};

// Sort specification for a single column
struct SortKey {
  size_t column_index;
  SortDirection direction = SortDirection::kAscending;
  NullsOrder nulls_order = NullsOrder::kLast;
};

// Column-wise sort operator using optimized radix sort
// Implements: ORDER BY column(s) [ASC|DESC] [NULLS FIRST|LAST]
class SortOp : public TransformOperator {
 public:
  // Sort by a single column
  SortOp(std::unique_ptr<Operator> child, size_t sort_column,
         SortDirection direction = SortDirection::kAscending)
      : TransformOperator(std::move(child)),
        sort_keys_{{sort_column, direction, NullsOrder::kLast}} {}

  // Sort by multiple columns
  explicit SortOp(std::unique_ptr<Operator> child,
                  std::vector<SortKey> sort_keys)
      : TransformOperator(std::move(child)), sort_keys_(std::move(sort_keys)) {}

  Status Prepare(ExecContext* ctx) override {
    // Phase 1: Collect all input chunks
    RETURN_IF_ERROR(CollectAllInput(ctx));

    // Phase 2: Perform sorting
    SortAllChunks();

    // Reset for output phase
    output_chunk_index_ = 0;
    output_row_index_ = 0;

    return Status::Ok();
  }

  Status Next(Chunk* out_chunk) override {
    if (sorted_data_.empty()) {
      is_finished_ = true;
      return Status::EndOfFile();
    }

    if (output_chunk_index_ >= sorted_data_.size()) {
      is_finished_ = true;
      return Status::EndOfFile();
    }

    // Copy data to output chunk
    auto* out = static_cast<KeyValueChunk*>(out_chunk);
    *out = std::move(sorted_data_[output_chunk_index_]);
    output_chunk_index_++;

    return Status::Ok();
  }

  size_t num_rows() const { return total_rows_; }

 private:
  // Collect all input into memory
  Status CollectAllInput(ExecContext* ctx) {
    KeyValueChunk chunk;
    while (true) {
      Status status = child()->Next(&chunk);
      if (status.code() == StatusCode::kEndOfFile) {
        break;
      }
      if (!status.ok()) {
        return status;
      }
      if (chunk.empty()) continue;

      // Clone the chunk into our storage
      auto cloned = MakeKeyValueChunk(chunk.num_rows());
      cloned.SetNumRows(chunk.num_rows());

      auto& src_keys = chunk.GetColumn<0>();
      auto& src_values = chunk.GetColumn<1>();
      auto& dst_keys = cloned.GetColumn<0>();
      auto& dst_values = cloned.GetColumn<1>();

      for (size_t i = 0; i < chunk.num_rows(); ++i) {
        dst_keys.ValueAt(i) = src_keys.ValueAt(i);
        dst_values.ValueAt(i) = src_values.ValueAt(i);
      }

      input_chunks_.push_back(std::move(cloned));
      total_rows_ += chunk.num_rows();
    }

    return Status::Ok();
  }

  // Perform sorting on all collected data
  void SortAllChunks() {
    if (input_chunks_.empty()) return;

    // Calculate total size and flatten data
    std::vector<int32_t> all_keys;
    std::vector<int64_t> all_values;

    for (auto& chunk : input_chunks_) {
      auto& keys = chunk.GetColumn<0>();
      auto& values = chunk.GetColumn<1>();
      for (size_t i = 0; i < chunk.num_rows(); ++i) {
        all_keys.push_back(keys.ValueAt(i));
        all_values.push_back(values.ValueAt(i));
      }
    }

    // Create index array and sort using std::sort with custom comparator
    // This preserves key-value pairing correctly
    std::vector<size_t> indices(all_keys.size());
    std::iota(indices.begin(), indices.end(), 0);

    if (!sort_keys_.empty() && sort_keys_[0].direction == SortDirection::kAscending) {
      std::sort(indices.begin(), indices.end(),
                [&](size_t a, size_t b) { return all_keys[a] < all_keys[b]; });
    } else {
      std::sort(indices.begin(), indices.end(),
                [&](size_t a, size_t b) { return all_keys[a] > all_keys[b]; });
    }

    // Reorder keys and values using sorted indices
    std::vector<int32_t> sorted_keys(all_keys.size());
    std::vector<int64_t> sorted_values(all_values.size());

    for (size_t i = 0; i < indices.size(); ++i) {
      sorted_keys[i] = all_keys[indices[i]];
      sorted_values[i] = all_values[indices[i]];
    }

    all_keys.swap(sorted_keys);
    all_values.swap(sorted_values);

    // Re-chunk the sorted data
    const size_t kChunkSize = 4096;
    for (size_t i = 0; i < all_keys.size(); i += kChunkSize) {
      size_t count = std::min(kChunkSize, all_keys.size() - i);
      auto chunk = MakeKeyValueChunk(count);
      chunk.SetNumRows(count);

      auto& keys = chunk.GetColumn<0>();
      auto& values = chunk.GetColumn<1>();

      for (size_t j = 0; j < count; ++j) {
        keys.ValueAt(j) = all_keys[i + j];
        values.ValueAt(j) = all_values[i + j];
      }

      sorted_data_.push_back(std::move(chunk));
    }

    input_chunks_.clear();
  }

  std::vector<SortKey> sort_keys_;
  std::vector<KeyValueChunk> input_chunks_;
  std::vector<KeyValueChunk> sorted_data_;
  size_t output_chunk_index_ = 0;
  size_t output_row_index_ = 0;
  size_t total_rows_ = 0;
};

// Top-N operator: returns the N smallest/largest rows
// More efficient than full sort when N << total rows
class TopNOp : public TransformOperator {
 public:
  TopNOp(std::unique_ptr<Operator> child, size_t n,
         size_t sort_column = 0,
         SortDirection direction = SortDirection::kAscending)
      : TransformOperator(std::move(child)),
        n_(n),
        sort_column_(sort_column),
        direction_(direction) {}

  Status Prepare(ExecContext* ctx) override {
    RETURN_IF_ERROR(CollectAndFindTopN(ctx));
    output_index_ = 0;
    return Status::Ok();
  }

  Status Next(Chunk* out_chunk) override {
    if (output_index_ >= results_.size()) {
      is_finished_ = true;
      return Status::EndOfFile();
    }

    auto* out = static_cast<KeyValueChunk*>(out_chunk);
    *out = std::move(results_[output_index_]);
    output_index_++;

    return Status::Ok();
  }

  size_t num_rows() const { return total_result_rows_; }

 private:
  Status CollectAndFindTopN(ExecContext* ctx) {
    // Collect all keys and values first
    KeyValueChunk chunk;
    std::vector<int32_t> all_keys;
    std::vector<int64_t> all_values;

    while (true) {
      Status status = child()->Next(&chunk);
      if (status.code() == StatusCode::kEndOfFile) {
        break;
      }
      if (!status.ok()) {
        return status;
      }
      if (chunk.empty()) continue;

      auto& keys = chunk.GetColumn<0>();
      auto& values = chunk.GetColumn<1>();

      for (size_t i = 0; i < chunk.num_rows(); ++i) {
        all_keys.push_back(keys.ValueAt(i));
        all_values.push_back(values.ValueAt(i));
      }
    }

    // Use partial_sort to get top N
    size_t actual_n = std::min(n_, all_keys.size());

    if (direction_ == SortDirection::kAscending) {
      // For smallest N: use partial_sort with ascending comparator
      std::partial_sort(
          all_keys.begin(), all_keys.begin() + actual_n, all_keys.end(),
          [](int32_t a, int32_t b) { return a < b; });
    } else {
      // For largest N: use partial_sort with descending comparator
      std::partial_sort(
          all_keys.begin(), all_keys.begin() + actual_n, all_keys.end(),
          [](int32_t a, int32_t b) { return a > b; });
    }

    // Collect top N with their values
    top_keys_.clear();
    top_values_.clear();
    top_keys_.reserve(actual_n);
    top_values_.reserve(actual_n);

    for (size_t i = 0; i < actual_n; ++i) {
      // Find the value that corresponds to this key
      // Since values may not be unique, we need to track indices
      top_keys_.push_back(all_keys[i]);
    }

    // For the values, we need to re-extract them correctly
    // Create a combined vector of pairs, sort, then extract
    std::vector<std::pair<int32_t, int64_t>> pairs;
    pairs.reserve(all_keys.size());
    for (size_t i = 0; i < all_keys.size(); ++i) {
      pairs.emplace_back(all_keys[i], all_values[i]);
    }

    if (direction_ == SortDirection::kAscending) {
      std::partial_sort(
          pairs.begin(), pairs.begin() + actual_n, pairs.end(),
          [](const auto& a, const auto& b) { return a.first < b.first; });
    } else {
      std::partial_sort(
          pairs.begin(), pairs.begin() + actual_n, pairs.end(),
          [](const auto& a, const auto& b) { return a.first > b.first; });
    }

    top_keys_.clear();
    top_values_.clear();
    for (size_t i = 0; i < actual_n; ++i) {
      top_keys_.push_back(pairs[i].first);
      top_values_.push_back(pairs[i].second);
    }

    // Create output chunks
    const size_t kChunkSize = 4096;
    for (size_t i = 0; i < top_keys_.size(); i += kChunkSize) {
      size_t count = std::min(kChunkSize, top_keys_.size() - i);
      auto out_chunk = MakeKeyValueChunk(count);
      out_chunk.SetNumRows(count);

      auto& keys = out_chunk.GetColumn<0>();
      auto& values = out_chunk.GetColumn<1>();

      for (size_t j = 0; j < count; ++j) {
        keys.ValueAt(j) = top_keys_[i + j];
        values.ValueAt(j) = top_values_[i + j];
      }

      results_.push_back(std::move(out_chunk));
      total_result_rows_ += count;
    }

    return Status::Ok();
  }

  size_t n_;
  size_t sort_column_;
  SortDirection direction_;

  std::vector<int32_t> top_keys_;
  std::vector<int64_t> top_values_;
  std::vector<KeyValueChunk> results_;
  size_t output_index_ = 0;
  size_t total_result_rows_ = 0;
};

}  // namespace vagg

#endif  // VAGG_OPS_SORT_OP_H_
