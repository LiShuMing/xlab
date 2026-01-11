#ifndef WSTP_CACHE_PADDING_H_
#define WSTP_CACHE_PADDING_H_

#include <cstddef>

namespace wstp {

// Cache line size on most modern CPUs (including Apple Silicon)
inline constexpr size_t kCacheLineSize = 64;

// Align to cache line boundary to prevent false sharing
#define WSTP_CACHELINE_ALIGN alignas(kCacheLineSize)

// Pad a struct member to fill a cache line
// Usage: WSTP_CACHELINE_ALIGN int counter;
//
// For padding between members:
// struct Foo {
//   int a;
//   WSTP_CACHELINE_PADDING(1);  // Adds 63 bytes of padding
//   int b;
// };

// Helper to create padding
template <size_t N = kCacheLineSize>
struct CachePadding {
  char padding[N];
};

// Insert padding to align to next cache line
#define WSTP_CACHELINE_PADDING(count) \
  CachePadding<kCacheLineSize - ((count) % kCacheLineSize)> padding_after_

}  // namespace wstp

#endif  // WSTP_CACHE_PADDING_H_
