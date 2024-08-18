#pragma once

#include <functional>

namespace xlab {

  namespace inner {

    /// everyone
    template <typename T>
    inline void hash_combine(size_t& seed, const T& val) {
      seed ^= std::hash<T>()(val) + 0x9e3779b9 + (seed<<6) + (seed>>2);
    }

    /// last
    template <typename T>
    inline void hash(size_t& seed, const T& val) {
      hash_combine(seed, val);
    }

    /// recursive
    template <typename T, typename... Types>
    inline void hash(size_t& seed, const T& val, const Types&... args) {
      hash_combine(seed, val);
      hash(seed, args...);
    }

  } // namespace inner

  template <typename... Types>
  inline size_t hash(const Types&... args) {
    size_t seed = 0;
    inner::hash(seed, args...);
    return seed;
  }

} // namespace chef

#endif // _CHEF_BASE_HASH_HPP_
