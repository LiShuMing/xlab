#ifndef VAGG_OPS_SINK_OP_H_
#define VAGG_OPS_SINK_OP_H_

#include <iostream>

#include "vagg/exec/operator.h"
#include "vagg/vector/chunk.h"

namespace vagg {

// Sink operator - consumes output, prints or collects results
class SinkOp : public SinkOperator {
 public:
  explicit SinkOp(std::unique_ptr<Operator> child, bool print_output = true)
      : SinkOperator(std::move(child)), print_output_(print_output) {}

  Status Prepare(ExecContext* ctx) override {
    num_rows_ = 0;
    return child()->Prepare(ctx);
  }

  Status Next(Chunk* out_chunk) override {
    Status status = child()->Next(out_chunk);
    if (status.code() == StatusCode::kEndOfFile) {
      is_finished_ = true;
      if (print_output_) {
        std::cout << "Total rows: " << num_rows_ << std::endl;
      }
      return Status::EndOfFile();
    }
    if (!status.ok()) {
      return status;
    }

    if (!out_chunk->empty()) {
      num_rows_ += out_chunk->num_rows();
      if (print_output_) {
        PrintChunk(out_chunk);
      }
    }

    return Status::Ok();
  }

  size_t num_rows() const { return num_rows_; }

 private:
  void PrintChunk(Chunk* chunk) {
    auto* kv_chunk = static_cast<KeyValueChunk*>(chunk);
    auto& keys = kv_chunk->template GetColumn<0>();
    auto& values = kv_chunk->template GetColumn<1>();
    size_t n = kv_chunk->num_rows();

    for (size_t i = 0; i < n; ++i) {
      std::cout << keys.ValueAt(i) << "\t" << values.ValueAt(i) << std::endl;
    }
  }

  bool print_output_;
  size_t num_rows_ = 0;
};

// Result collector - collects all output into memory
class ResultCollectorOp : public SinkOperator {
 public:
  explicit ResultCollectorOp(std::unique_ptr<Operator> child)
      : SinkOperator(std::move(child)) {}

  Status Prepare(ExecContext* ctx) override {
    result_keys_.clear();
    result_values_.clear();
    return child()->Prepare(ctx);
  }

  Status Next(Chunk* out_chunk) override {
    Status status = child()->Next(out_chunk);
    if (status.code() == StatusCode::kEndOfFile) {
      is_finished_ = true;
      return Status::EndOfFile();
    }
    if (!status.ok()) {
      return status;
    }

    if (!out_chunk->empty()) {
      auto* kv_chunk = static_cast<KeyValueChunk*>(out_chunk);
      auto& keys = kv_chunk->template GetColumn<0>();
      auto& values = kv_chunk->template GetColumn<1>();
      size_t n = kv_chunk->num_rows();

      for (size_t i = 0; i < n; ++i) {
        result_keys_.push_back(keys.ValueAt(i));
        result_values_.push_back(values.ValueAt(i));
      }
    }

    return Status::Ok();
  }

  const std::vector<int32_t>& result_keys() const { return result_keys_; }
  const std::vector<int64_t>& result_values() const { return result_values_; }
  size_t num_rows() const { return result_keys_.size(); }

 private:
  std::vector<int32_t> result_keys_;
  std::vector<int64_t> result_values_;
};

}  // namespace vagg

#endif  // VAGG_OPS_SINK_OP_H_
