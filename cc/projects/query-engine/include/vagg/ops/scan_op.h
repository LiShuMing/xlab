#ifndef VAGG_OPS_SCAN_OP_H_
#define VAGG_OPS_SCAN_OP_H_

#include <functional>
#include <random>

#include "vagg/exec/operator.h"
#include "vagg/vector/chunk.h"

namespace vagg {

// Data source interface
class DataSource {
 public:
  virtual ~DataSource() = default;
  virtual Status NextChunk(KeyValueChunk* out) = 0;
  virtual bool HasMore() const = 0;
  virtual void Reset() = 0;
};

// In-memory data source for testing/benchmarking
class MemoryDataSource : public DataSource {
 public:
  MemoryDataSource(const std::vector<int32_t>& keys,
                   const std::vector<int64_t>& values,
                   size_t batch_size = 1024)
      : keys_(keys), values_(values), batch_size_(batch_size), position_(0) {}

  Status NextChunk(KeyValueChunk* out) override {
    if (position_ >= keys_.size()) {
      return Status::EndOfFile();
    }

    size_t remaining = keys_.size() - position_;
    size_t count = std::min(batch_size_, remaining);

    auto& key_vec = out->template GetColumn<0>();
    auto& value_vec = out->template GetColumn<1>();

    key_vec.Resize(count);
    value_vec.Resize(count);

    for (size_t i = 0; i < count; ++i) {
      key_vec.ValueAt(i) = keys_[position_ + i];
      value_vec.ValueAt(i) = values_[position_ + i];
    }

    out->SetNumRows(count);
    position_ += count;

    return Status::Ok();
  }

  bool HasMore() const override { return position_ < keys_.size(); }

  void Reset() override { position_ = 0; }

 private:
  std::vector<int32_t> keys_;
  std::vector<int64_t> values_;
  size_t batch_size_;
  size_t position_;
};

// Simple Zipf-like distribution using inverse transform sampling
// Returns values in [1, n] with Zipf distribution
class SimpleZipf {
 public:
  SimpleZipf(uint32_t n, double s = 1.0, uint32_t seed = 0)
      : n_(n), s_(s), rng_(seed) {
    // Pre-compute normalization constant
    harmonic_ = 0.0;
    for (uint32_t i = 1; i <= n_; ++i) {
      harmonic_ += std::pow(static_cast<double>(i), -s_);
    }
  }

  uint32_t operator()() {
    // Generate uniform random in (0, 1]
    std::uniform_real_distribution<double> dist(0.0, 1.0);
    double x = dist(rng_) * harmonic_;

    // Find i such that sum_{j=1}^{i} j^(-s) >= x
    double sum = 0.0;
    for (uint32_t i = 1; i <= n_; ++i) {
      sum += std::pow(static_cast<double>(i), -s_);
      if (sum >= x) {
        return i;
      }
    }
    return n_;
  }

 private:
  uint32_t n_;
  double s_;
  double harmonic_;
  std::mt19937 rng_;
};

// Generated data source for testing/benchmarking
class GeneratedDataSource : public DataSource {
 public:
  enum class Distribution { kUniform, kZipf, kSequential };

  GeneratedDataSource(size_t num_rows, size_t batch_size,
                      Distribution dist = Distribution::kUniform,
                      int32_t key_range = 1000000)
      : num_rows_(num_rows),
        batch_size_(batch_size),
        distribution_(dist),
        key_range_(key_range),
        position_(0),
        rng_(std::random_device{}()),
        uniform_dist_(0, key_range - 1),
        value_dist_(1, 100),
        zipf_(key_range, 1.0, 0) {}  // Will re-seed

  Status NextChunk(KeyValueChunk* out) override {
    if (position_ >= num_rows_) {
      return Status::EndOfFile();
    }

    size_t count = std::min(batch_size_, num_rows_ - position_);

    auto& key_vec = out->template GetColumn<0>();
    auto& value_vec = out->template GetColumn<1>();

    key_vec.Resize(count);
    value_vec.Resize(count);

    for (size_t i = 0; i < count; ++i) {
      key_vec.ValueAt(i) = NextKey();
      value_vec.ValueAt(i) = NextValue();
    }

    out->SetNumRows(count);
    position_ += count;

    return Status::Ok();
  }

  bool HasMore() const override { return position_ < num_rows_; }

  void Reset() override { position_ = 0; }

 private:
  int32_t NextKey() {
    switch (distribution_) {
      case Distribution::kUniform:
        return static_cast<int32_t>(uniform_dist_(rng_));
      case Distribution::kZipf:
        return static_cast<int32_t>(zipf_());
      case Distribution::kSequential:
        return static_cast<int32_t>(position_ % key_range_);
    }
    return 0;
  }

  int64_t NextValue() {
    return static_cast<int64_t>(value_dist_(rng_));
  }

  size_t num_rows_;
  size_t batch_size_;
  Distribution distribution_;
  int32_t key_range_;
  size_t position_;
  std::mt19937 rng_;
  std::uniform_int_distribution<int32_t> uniform_dist_;
  std::uniform_int_distribution<int64_t> value_dist_;
  SimpleZipf zipf_;
};

// Scan operator - reads from a data source
class ScanOp : public SourceOperator {
 public:
  explicit ScanOp(std::unique_ptr<DataSource> source)
      : source_(std::move(source)) {}

  Status Prepare(ExecContext* ctx) override {
    source_->Reset();
    return Status::Ok();
  }

  Status Next(Chunk* out_chunk) override {
    // Write directly to output chunk (caller must provide KeyValueChunk)
    auto* kv_chunk = static_cast<KeyValueChunk*>(out_chunk);
    Status status = source_->NextChunk(kv_chunk);
    if (!status.ok() && status.code() != StatusCode::kEndOfFile) {
      return status;
    }
    if (status.code() == StatusCode::kEndOfFile) {
      is_finished_ = true;
      return Status::EndOfFile();
    }
    return Status::Ok();
  }

 private:
  std::unique_ptr<DataSource> source_;
};

}  // namespace vagg

#endif  // VAGG_OPS_SCAN_OP_H_
