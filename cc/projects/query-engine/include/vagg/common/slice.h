#ifndef VAGG_COMMON_SLICE_H_
#define VAGG_COMMON_SLICE_H_

#include <cstddef>
#include <cstring>
#include <span>
#include <stdexcept>

namespace vagg {

// Simple slice/view for contiguous memory
template <typename T>
class Slice {
 public:
  Slice() : data_(nullptr), size_(0) {}

  Slice(T* data, size_t size) : data_(data), size_(size) {}

  // From std::span
  explicit Slice(std::span<T> span) : data_(span.data()), size_(span.size()) {}

  T& operator[](size_t index) {
    if (index >= size_) {
      throw std::out_of_range("Slice index out of range");
    }
    return data_[index];
  }

  const T& operator[](size_t index) const {
    if (index >= size_) {
      throw std::out_of_range("Slice index out of range");
    }
    return data_[index];
  }

  T* data() { return data_; }
  const T* data() const { return data_; }
  size_t size() const { return size_; }
  bool empty() const { return size_ == 0; }

  T& front() {
    if (empty()) throw std::out_of_range("Empty slice");
    return data_[0];
  }

  T& back() {
    if (empty()) throw std::out_of_range("Empty slice");
    return data_[size_ - 1];
  }

  std::span<T> span() { return std::span<T>(data_, size_); }
  std::span<const T> span() const { return std::span<const T>(data_, size_); }

  // Sub-slice [start, end)
  Slice<T> SubSlice(size_t start, size_t end) const {
    if (start > end || end > size_) {
      throw std::out_of_range("Invalid sub-slice range");
    }
    return Slice<T>(data_ + start, end - start);
  }

 private:
  T* data_;
  size_t size_;
};

}  // namespace vagg

#endif  // VAGG_COMMON_SLICE_H_
