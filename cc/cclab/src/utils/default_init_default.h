
#pragma once

#include <memory>
#include <type_traits>
#include <utility>
#include <vector>

// C++ Reference recommend to use this allocator implementation to
// prevent containers resize invocation from initializing the allocated
// memory space unnecessarily.
// https://stackoverflow.com/questions/21028299/is-this-behavior-of-vectorresizesize-type-n-under-c11-and-boost-container/21028912#21028912
// Allocator adaptor that interposes construct() calls to
// convert value initialization into default initialization.
template <typename T, typename A = std::allocator<T>>
class default_init_allocator : public A {
    typedef std::allocator_traits<A> at;

public:
    template <typename U>
    struct rebind {
        using other = default_init_allocator<U, typename at::template rebind_alloc<U>>;
    };

    using A::A;

    template <typename U>
    void construct(U* ptr) noexcept(std::is_nothrow_default_constructible<U>::value) {
        ::new (static_cast<void*>(ptr)) U;
    }

    template <typename U, typename... Args>
    void construct(U* ptr, Args&&... args) {
        at::construct(static_cast<A&>(*this), ptr, std::forward<Args>(args)...);
    }
};

namespace raw {

using raw_string = std::basic_string<char, std::char_traits<char>, default_init_allocator<char>>;

template <class T, std::enable_if_t<std::is_trivially_destructible_v<T>, T> = 0>
using raw_vector = std::vector<T, default_init_allocator<T>>;

} // namespace raw
