#ifndef RINGSERVER_COMMON_LIKELY_HPP_
#define RINGSERVER_COMMON_LIKELY_HPP_

// Branch prediction hints for hot path optimization
#if defined(__GNUC__) || defined(__clang__)
#define RINGSERVER_LIKELY(x) __builtin_expect(!!(x), 1)
#define RINGSERVER_UNLIKELY(x) __builtin_expect(!!(x), 0)
#else
#define RINGSERVER_LIKELY(x) (x)
#define RINGSERVER_UNLIKELY(x) (x)
#endif

// Compile-time assertions
#define RINGSERVER_CONCAT_IMPL(x, y) x##y
#define RINGSERVER_CONCAT(x, y) RINGSERVER_CONCAT_IMPL(x, y)
#define RINGSERVER_STATIC_ASSERT(expr, msg) \
    static_assert(expr, msg)

// Disable copy for class
#define RINGSERVER_DISALLOW_COPY(TypeName) \
    TypeName(const TypeName&) = delete; \
    TypeName& operator=(const TypeName&) = delete;

// Move-only for class
#define RINGSERVER_DISALLOW_COPY_AND_MOVE(TypeName) \
    TypeName(const TypeName&) = delete; \
    TypeName(TypeName&&) = delete; \
    TypeName& operator=(const TypeName&) = delete; \
    TypeName& operator=(TypeName&&) = delete;

#endif  // RINGSERVER_COMMON_LIKELY_HPP_
