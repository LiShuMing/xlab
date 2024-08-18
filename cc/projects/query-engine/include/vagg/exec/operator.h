#ifndef VAGG_EXEC_OPERATOR_H_
#define VAGG_EXEC_OPERATOR_H_

#include <memory>

#include "vagg/common/status.h"
#include "vagg/vector/chunk.h"

namespace vagg {

// Forward declaration
class Operator;

// Execution context for operators
class ExecContext {
 public:
  ExecContext() = default;
  virtual ~ExecContext() = default;
};

// Base operator interface
class Operator {
 public:
  virtual ~Operator() = default;

  // Prepare the operator (called once before iteration)
  virtual Status Prepare(ExecContext* ctx) = 0;

  // Get the next chunk, returns EndOfFile when done
  // out_chunk must be empty on success to receive data
  virtual Status Next(Chunk* out_chunk) = 0;

  // Get the child operator (if any)
  virtual Operator* child() const { return nullptr; }

  // Check if operator is finished
  bool IsFinished() const { return is_finished_; }

 protected:
  bool is_finished_ = false;
};

// Source operator (leaf)
class SourceOperator : public Operator {
 public:
  Operator* child() const override { return nullptr; }
};

// Transform operator (has child)
class TransformOperator : public Operator {
 public:
  explicit TransformOperator(std::unique_ptr<Operator> child)
      : child_(std::move(child)) {}

  Operator* child() const override { return child_.get(); }

 protected:
  std::unique_ptr<Operator> child_;
};

// Sink operator (terminates pipeline)
class SinkOperator : public Operator {
 public:
  explicit SinkOperator(std::unique_ptr<Operator> child)
      : child_(std::move(child)) {}

  Operator* child() const override { return child_.get(); }

 protected:
  std::unique_ptr<Operator> child_;
};

}  // namespace vagg

#endif  // VAGG_EXEC_OPERATOR_H_
