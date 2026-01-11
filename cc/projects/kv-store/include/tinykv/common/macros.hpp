#ifndef TINYKV_COMMON_MACROS_HPP_
#define TINYKV_COMMON_MACROS_HPP_

// Disable copy and assignment operators
#define DISALLOW_COPY(TypeName) \
    TypeName(const TypeName&) = delete; \
    TypeName& operator=(const TypeName&) = delete;

// Disable copy, allow move
#define DISALLOW_COPY_MOVE(TypeName) \
    DISALLOW_COPY(TypeName) \
    TypeName(TypeName&&) = delete; \
    TypeName& operator=(TypeName&&) = delete;

// Allow copy and move (default)
#define ALLOW_COPY_MOVE(TypeName) \
    TypeName(const TypeName&) = default; \
    TypeName& operator=(const TypeName&) = default; \
    TypeName(TypeName&&) = default; \
    TypeName& operator=(TypeName&&) = default;

// Lint annotations
#if defined(__clang__) || defined(__GNUC__)
#define TINYKV_LIKELY(x) __builtin_expect(!!(x), 1)
#define TINYKV_UNLIKELY(x) __builtin_expect(!!(x), 0)
#else
#define TINYKV_LIKELY(x) (x)
#define TINYKV_UNLIKELY(x) (x)
#endif

#endif  // TINYKV_COMMON_MACROS_HPP_
