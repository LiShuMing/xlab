#include "../include/fwd.h"
#include <cstddef>
#include <cstring>

namespace algo {

// Safe memory copy - handles overlapping regions
// memmove allows source and destination memory regions to overlap
// Core principle:
// 1. If destination address < source address, copy forward from low to high addresses
// 2. If destination address > source address (overlap case), copy backward from high to low addresses
void* l_memmove(void* dst, const void* src, size_t len) {
    if (dst == nullptr || src == nullptr || len == 0) {
        return dst;
    }

    auto d = static_cast<unsigned char*>(dst);
    auto s = static_cast<const unsigned char*>(src);

    // Check for overlap:
    // - No overlap or forward overlap (dest before source): forward copy
    // - Backward overlap (dest within or after source): backward copy
    if (d < s) {
        // Forward copy
        for (size_t i = 0; i < len; ++i) {
            d[i] = s[i];
        }
    } else {
        // Backward copy: start from high address to avoid overwriting source data not yet copied
        for (size_t i = len; i > 0; --i) {
            d[i - 1] = s[i - 1];
        }
    }

    return dst;
}

// Simple memcpy (does not handle overlap)
// Note: Standard library memcpy has undefined behavior when regions overlap
void* l_memcpy(void* dst, const void* src, size_t len) {
    if (dst == nullptr || src == nullptr || len == 0) {
        return dst;
    }

    auto d = static_cast<unsigned char*>(dst);
    auto s = static_cast<const unsigned char*>(src);

    // Simple byte-by-byte forward copy
    for (size_t i = 0; i < len; ++i) {
        d[i] = s[i];
    }

    return dst;
}

// Test function
void test_memmove() {
    // Test case 1: non-overlapping regions
    char buf1[] = "Hello, World!";
    l_memmove(buf1 + 7, buf1, 5);  // "Hello, Hello!"
    // Result: buf1 = "Hello, Hello!"

    // Test case 2: complete overlap (backward copy)
    char buf2[] = "ABCDEFG";
    l_memmove(buf2 + 2, buf2, 4);  // "ABABCFG"
    // Process:
    // Forward copy wrong example: dst[2]=A, dst[3]=B, dst[4]=C, dst[5]=D
    //                            Result: "AABCFG" (A copied multiple times)
    // Backward copy: correct: dst[5]=D, dst[4]=C, dst[3]=B, dst[2]=A
    //                 Result: "ABABCFG"

    // Test case 3: complete overlap (forward copy)
    char buf3[] = "ABCDEFG";
    l_memmove(buf3, buf3 + 2, 4);  // "CDEEFG"
    // Forward copy: correct

    (void)buf1;
    (void)buf2;
    (void)buf3;
}
void test_memcpy() {
    char buf1[] = "Hello, World!";
    l_memcpy(buf1 + 7, buf1, 5);  // "Hello, Hello!"
    // Result: buf1 = "Hello, Hello!"
    (void)buf1;
}

int main() {
    test_memmove();
    return 0;
}

}  // namespace algo