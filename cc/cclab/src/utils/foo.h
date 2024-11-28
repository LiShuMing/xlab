#pragma once
#ifndef FOO_H
#define FOO_H
#include<vector>
namespace detail {

static int add(int a, int b) {
    return a + b;
}

class Functions {
public:
    // Test how to build a seperate header/source template function.
    template <bool a>
    static bool func1();
};

template<> bool Functions::func1<true>();
template<> bool Functions::func1<false>();

} // namespace detail
#endif // MY_HEADER_H