#include<vector>

int add(int a, int b) {
    return a + b;
}

namespace detail {

class Functions {
public:
    // Test how to build a seperate header/source template function.
    template <bool a>
    static bool func1();
};

template<> bool Functions::func1<true>();
template<> bool Functions::func1<false>();

} // namespace detail