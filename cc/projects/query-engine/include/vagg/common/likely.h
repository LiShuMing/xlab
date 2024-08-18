#ifndef VAGG_COMMON_LIKELY_H_
#define VAGG_COMMON_LIKELY_H_

// Branch prediction hints for performance
#if defined(__GNUC__) || defined(__clang__)
#define VAGG_LIKELY(x) __builtin_expect(!!(x), 1)
#define VAGG_UNLIKELY(x) __builtin_expect(!!(x), 0)
#else
#define VAGG_LIKELY(x) (x)
#define VAGG_UNLIKELY(x) (x)
#endif

// Cache line size for alignment
inline constexpr size_t VAGG_CACHE_LINE_SIZE = 64;

#define VAGG_CACHELINE_ALIGN alignas(VAGG_CACHE_LINE_SIZE)

#endif  // VAGG_COMMON_LIKELY_H_
