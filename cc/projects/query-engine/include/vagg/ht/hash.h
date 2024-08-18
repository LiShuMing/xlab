#ifndef VAGG_HT_HASH_H_
#define VAGG_HT_HASH_H_

#include <cstdint>

namespace vagg {

// Hash functions for common types
// Using splitmix64 for good distribution

// SplitMix64 hash function - good quality, fast
inline uint64_t SplitMix64(uint64_t x) {
  x += 0x9e3779b97f4a7c15ULL;
  x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ULL;
  x = (x ^ (x >> 27)) * 0x94d049bb133111ebULL;
  return x ^ (x >> 31);
}

// Hash for uint64_t
inline uint64_t HashUInt64(uint64_t x) {
  return SplitMix64(x);
}

// Hash for int64_t (reinterpret as uint64_t)
inline uint64_t HashInt64(int64_t x) {
  return SplitMix64(static_cast<uint64_t>(x));
}

// Hash for int32_t (promote to uint64_t)
inline uint64_t HashInt32(int32_t x) {
  return SplitMix64(static_cast<uint64_t>(static_cast<uint32_t>(x)));
}

// Hash for uint32_t
inline uint64_t HashUInt32(uint32_t x) {
  return SplitMix64(static_cast<uint64_t>(x));
}

// Hash for double (bit pattern hash)
// Note: std::bit_cast requires C++20 and compiler support
// Using reinterpret_cast as fallback for AppleClang
inline uint64_t HashDouble(double x) {
  return SplitMix64(*reinterpret_cast<uint64_t*>(&x));
}

// Template for generic types - requires specialization
template <typename T>
inline uint64_t Hash(const T& value);

// Specializations
template <>
inline uint64_t Hash<int32_t>(const int32_t& value) {
  return HashInt32(value);
}

template <>
inline uint64_t Hash<int64_t>(const int64_t& value) {
  return HashInt64(value);
}

template <>
inline uint64_t Hash<uint32_t>(const uint32_t& value) {
  return HashUInt32(value);
}

template <>
inline uint64_t Hash<uint64_t>(const uint64_t& value) {
  return HashUInt64(value);
}

template <>
inline uint64_t Hash<double>(const double& value) {
  return HashDouble(value);
}

// Mix hash to reduce correlation
inline uint64_t MixHash(uint64_t hash, uint64_t seed = 0x9e3779b97f4a7c15ULL) {
  return hash ^ (seed + 0x9e3779b97f4a7c15ULL + (hash << 6) + (hash >> 2));
}

}  // namespace vagg

#endif  // VAGG_HT_HASH_H_
