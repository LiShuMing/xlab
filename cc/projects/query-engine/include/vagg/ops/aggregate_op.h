#ifndef VAGG_OPS_AGGREGATE_OP_H_
#define VAGG_OPS_AGGREGATE_OP_H_

#include <memory>
#include <unordered_map>
#include <vector>

#include "vagg/exec/operator.h"
#include "vagg/ht/hash_table.h"
#include "vagg/vector/chunk.h"

namespace vagg {

// Aggregate function interface
class AggregateFunction {
 public:
  virtual ~AggregateFunction() = default;
  virtual void Initialize() = 0;
  virtual void Update(int64_t value) = 0;
  virtual int64_t Finalize() const = 0;
  virtual void Merge(const AggregateFunction& other) = 0;
};

// Sum aggregation
class SumAggregate : public AggregateFunction {
 public:
  void Initialize() override { sum_ = 0; }
  void Update(int64_t value) override { sum_ += value; }
  int64_t Finalize() const override { return sum_; }
  void Merge(const AggregateFunction& other) override {
    sum_ += static_cast<const SumAggregate&>(other).sum_;
  }

 private:
  int64_t sum_ = 0;
};

// Count aggregation
class CountAggregate : public AggregateFunction {
 public:
  void Initialize() override { count_ = 0; }
  void Update(int64_t) override { ++count_; }
  int64_t Finalize() const override { return count_; }
  void Merge(const AggregateFunction& other) override {
    count_ += static_cast<const CountAggregate&>(other).count_;
  }

 private:
  int64_t count_ = 0;
};

// Hash aggregation operator
// SELECT key, SUM(value) FROM table GROUP BY key
class HashAggregateOp : public TransformOperator {
 public:
  HashAggregateOp(std::unique_ptr<Operator> child, size_t group_key_index = 0,
                  size_t aggregate_value_index = 1)
      : TransformOperator(std::move(child)),
        group_key_index_(group_key_index),
        aggregate_value_index_(aggregate_value_index),
        input_chunk_(MakeKeyValueChunk(4096)) {
    // Initialize hash table
    HashTableConfig config;
    config.capacity = 16384;  // Initial capacity
    config.max_load_factor = 0.7;
    ht_ = std::make_unique<Int32Int64HashTable>(config);
  }

  Status Prepare(ExecContext* ctx) override {
    // Build phase: consume all input
    KeyValueChunk chunk;
    Status status;

    while (true) {
      status = child()->Next(&chunk);
      if (status.code() == StatusCode::kEndOfFile) {
        break;
      }
      if (!status.ok()) {
        return status;
      }

      if (chunk.empty()) {
        continue;
      }

      // Process the chunk
      ProcessChunk(&chunk);
    }

    // Build output chunks from hash table
    BuildOutputChunks();

    // Reset for output phase
    output_index_ = 0;
    is_finished_ = true;  // Done building

    return Status::Ok();
  }

  Status Next(Chunk* out_chunk) override {
    if (output_index_ >= output_chunks_.size()) {
      is_finished_ = true;
      return Status::EndOfFile();
    }

    // Write directly to output chunk (caller must provide KeyValueChunk)
    auto* kv_chunk = static_cast<KeyValueChunk*>(out_chunk);
    *kv_chunk = std::move(output_chunks_[output_index_]);
    output_index_++;
    return Status::Ok();
  }

  // Get aggregation statistics
  HashTableStats GetHashTableStats() const { return ht_->GetStats(); }

 private:
  void ProcessChunk(KeyValueChunk* chunk) {
    auto& keys = chunk->template GetColumn<0>();
    auto& values = chunk->template GetColumn<1>();
    size_t num_rows = chunk->num_rows();

    for (size_t i = 0; i < num_rows; ++i) {
      int32_t key = keys.ValueAt(i);
      int64_t value = values.ValueAt(i);

      // Find or insert in hash table
      auto* entry = ht_->FindOrInsert(key);

      // Sum the value
      entry->value += value;
    }
  }

  void BuildOutputChunks() {
    output_chunks_.clear();

    auto chunk = MakeKeyValueChunk(1024);
    size_t idx = 0;

    for (auto it = ht_->begin(); it != ht_->end(); ++it) {
      auto* entry = *it;
      if (!entry->occupied) continue;

      if (idx >= 1024) {
        output_chunks_.push_back(std::move(chunk));
        chunk = MakeKeyValueChunk(1024);
        idx = 0;
      }

      auto& keys = chunk.template GetColumn<0>();
      auto& values = chunk.template GetColumn<1>();

      keys.ValueAt(idx) = entry->key;
      values.ValueAt(idx) = entry->value;
      idx++;
    }

    if (idx > 0) {
      chunk.SetNumRows(idx);
      output_chunks_.push_back(std::move(chunk));
    }
  }

  size_t group_key_index_;
  size_t aggregate_value_index_;

  std::unique_ptr<Int32Int64HashTable> ht_;
  KeyValueChunk input_chunk_;
  std::vector<KeyValueChunk> output_chunks_;
  size_t output_index_ = 0;
};

// Simple hash aggregation using unordered_map (for comparison)
class SimpleHashAggregateOp : public TransformOperator {
 public:
  SimpleHashAggregateOp(std::unique_ptr<Operator> child)
      : TransformOperator(std::move(child)) {}

  Status Prepare(ExecContext* ctx) override {
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

      auto& keys = chunk.template GetColumn<0>();
      auto& values = chunk.template GetColumn<1>();
      size_t num_rows = chunk.num_rows();

      for (size_t i = 0; i < num_rows; ++i) {
        int32_t key = keys.ValueAt(i);
        int64_t value = values.ValueAt(i);
        result_[key] += value;
      }
    }

    // Build output
    output_keys_.reserve(result_.size());
    output_values_.reserve(result_.size());
    for (auto& [k, v] : result_) {
      output_keys_.push_back(k);
      output_values_.push_back(v);
    }

    output_index_ = 0;
    return Status::Ok();
  }

  Status Next(Chunk* out_chunk) override {
    if (output_index_ >= result_.size()) {
      is_finished_ = true;
      return Status::EndOfFile();
    }

    auto* kv_chunk = static_cast<KeyValueChunk*>(out_chunk);
    auto& keys = kv_chunk->template GetColumn<0>();
    auto& values = kv_chunk->template GetColumn<1>();

    size_t count = std::min(static_cast<size_t>(1024), result_.size() - output_index_);
    keys.Resize(count);
    values.Resize(count);

    for (size_t i = 0; i < count; ++i) {
      keys.ValueAt(i) = output_keys_[output_index_ + i];
      values.ValueAt(i) = output_values_[output_index_ + i];
    }

    out_chunk->SetNumRows(count);
    output_index_ += count;
    return Status::Ok();
  }

 private:
  std::unordered_map<int32_t, int64_t> result_;
  std::vector<int32_t> output_keys_;
  std::vector<int64_t> output_values_;
  size_t output_index_ = 0;
};

}  // namespace vagg

#endif  // VAGG_OPS_AGGREGATE_OP_H_
