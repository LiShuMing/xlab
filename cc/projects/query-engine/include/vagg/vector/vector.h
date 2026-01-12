#ifndef VAGG_VECTOR_VECTOR_H_
#define VAGG_VECTOR_VECTOR_H_

#include <algorithm>
#include <bitset>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <vector>

#include "vagg/common/slice.h"

namespace vagg {

// Type for validity bitmap - 64 bits per word
using ValidityWord = uint64_t;
inline constexpr size_t kValidityBitsPerWord = 64;

// Simple validity bitmap for nullable columns
class ValidityBitmap {
 public:
  ValidityBitmap() : num_bits_(0), words_() {}

  explicit ValidityBitmap(size_t num_bits, bool valid = true) : num_bits_(num_bits) {
    size_t num_words = (num_bits + kValidityBitsPerWord - 1) / kValidityBitsPerWord;
    words_.resize(num_words);
    if (valid) {
      // All bits set means valid
      std::fill(words_.begin(), words_.end(), ~ValidityWord(0));
      // Clear unused bits in the last word
      if (num_bits_ % kValidityBitsPerWord != 0) {
        words_.back() &= (ValidityWord(1) << (num_bits_ % kValidityBitsPerWord)) - 1;
      }
    } else {
      // All bits clear means invalid
      std::fill(words_.begin(), words_.end(), ValidityWord(0));
    }
  }

  bool IsValid(size_t index) const {
    size_t word_idx = index / kValidityBitsPerWord;
    size_t bit_idx = index % kValidityBitsPerWord;
    return (words_[word_idx] >> bit_idx) & ValidityWord(1);
  }

  void SetValid(size_t index, bool valid) {
    size_t word_idx = index / kValidityBitsPerWord;
    size_t bit_idx = index % kValidityBitsPerWord;
    if (valid) {
      words_[word_idx] |= (ValidityWord(1) << bit_idx);
    } else {
      words_[word_idx] &= ~(ValidityWord(1) << bit_idx);
    }
  }

  size_t num_bits() const { return num_bits_; }
  size_t num_words() const { return words_.size(); }

  // Copy from another bitmap (with offset)
  void CopyFrom(const ValidityBitmap& src, size_t src_offset, size_t dst_offset, size_t count) {
    for (size_t i = 0; i < count; ++i) {
      SetValid(dst_offset + i, src.IsValid(src_offset + i));
    }
  }

 private:
  size_t num_bits_;
  std::vector<ValidityWord> words_;
};

// Selection vector for filtering/sparse indices
// Stores logical row indices to access in a vector
class SelectionVector {
 public:
  SelectionVector() : size_(0), data_() {}

  explicit SelectionVector(size_t capacity) : size_(0), data_(capacity) {}

  size_t size() const { return size_; }
  size_t capacity() const { return data_.size(); }

  uint32_t& operator[](size_t index) { return data_[index]; }
  const uint32_t& operator[](size_t index) const { return data_[index]; }

  uint32_t* data() { return data_.data(); }
  const uint32_t* data() const { return data_.data(); }

  void Append(uint32_t value) {
    if (size_ >= data_.size()) {
      size_t new_size = std::max(data_.size() * 2, size_t(64));
      data_.resize(new_size);
    }
    data_[size_++] = value;
  }

  void Resize(size_t new_size) { size_ = new_size; }

 private:
  size_t size_;
  std::vector<uint32_t> data_;
};

// Type enum for runtime type checking (must be before VectorBase)
enum class VectorType {
  kInt32,
  kInt64,
  kFloat64,
  kInt32Flat,
  kInt64Flat,
  kFloat64Flat,
};

// Base class for all vector types
class VectorBase {
 public:
  virtual ~VectorBase() = default;

  virtual VectorType type() const = 0;
  size_t size() const { return size_; }
  bool empty() const { return size_ == 0; }

 protected:
  size_t size_ = 0;
};

// FlatVector<T> - simple columnar vector with optional validity
template <typename T>
class FlatVector : public VectorBase {
 public:
  using value_type = T;

  FlatVector() : data_(), validity_() {}

  explicit FlatVector(size_t capacity) : data_(capacity), validity_(capacity, true) {
    size_ = capacity;
  }

  VectorType type() const override;

  // Resize to new size (preserves existing data)
  void Resize(size_t new_size) {
    size_ = new_size;
    if (data_.size() < new_size) {
      data_.resize(new_size);
    }
    if (validity_.num_bits() < new_size) {
      validity_ = ValidityBitmap(new_size, true);
    }
  }

  // Raw data access
  T* data() { return data_.data(); }
  const T* data() const { return data_.data(); }

  // Get value at index (no null check)
  T& ValueAt(size_t index) { return data_[index]; }
  const T& ValueAt(size_t index) const { return data_[index]; }

  // Validity access
  ValidityBitmap& validity() { return validity_; }
  const ValidityBitmap& validity() const { return validity_; }

  bool IsNull(size_t index) const { return !validity_.IsValid(index); }
  void SetNull(size_t index, bool is_null = true) { validity_.SetValid(index, !is_null); }

  // Slice access
  Slice<T> Slice(size_t offset, size_t length) {
    return Slice<T>(&data_[offset], length);
  }

 private:
  std::vector<T> data_;
  ValidityBitmap validity_;
};

// Template specializations for type()
template <>
inline VectorType FlatVector<int32_t>::type() const {
  return VectorType::kInt32Flat;
}

template <>
inline VectorType FlatVector<int64_t>::type() const {
  return VectorType::kInt64Flat;
}

template <>
inline VectorType FlatVector<double>::type() const {
  return VectorType::kFloat64Flat;
}

}  // namespace vagg

#endif  // VAGG_VECTOR_VECTOR_H_
