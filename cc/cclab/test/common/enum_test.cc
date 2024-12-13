#include <gtest/gtest.h>

#include <atomic>
#include <cassert>
#include <cstring>
#include <functional>
#include <iostream>
#include <thread>
#include <vector>

// Thread Test
class EnumTest : public testing::Test {
public:
  enum Color { RED, GREEN, BLUE };

  template <auto T> static void print_fn() {
#if __GNUC__ || __clang__
      std::cout << __PRETTY_FUNCTION__ << std::endl;
#elif _MSC_VER
      std::cout << __FUNCSIG__ << std::endl;
#endif
  }

template<auto value>
static constexpr auto enum_name(){
    std::string_view name;
#if __GNUC__ || __clang__
    name = __PRETTY_FUNCTION__;
    std::size_t start = name.find('=') + 2;
    std::size_t end = name.size() - 1;
    name = std::string_view{ name.data() + start, end - start };
    start = name.rfind("::");
#elif _MSC_VER
    name = __FUNCSIG__;
    std::size_t start = name.find('<') + 1;
    std::size_t end = name.rfind(">(");
    name = std::string_view{ name.data() + start, end - start };
    start = name.rfind("::");
#endif
    return start == std::string_view::npos ? name : std::string_view{
            name.data() + start + 2, name.size() - start - 2
    };
}

template <typename T, std::size_t N = 0> static constexpr auto enum_max() {
    constexpr auto value = static_cast<T>(N);
    if constexpr (enum_name<value>().find(")") == std::string_view::npos) {
        return enum_max<T, N + 1>();
    } else {
        return N;
    }
}

template <typename T>
    requires std::is_enum_v<T>
static constexpr auto enum_name(T value) {
    constexpr auto num = enum_max<T>();
    constexpr auto names = []<std::size_t... Is>(std::index_sequence<Is...>) {
        return std::array<std::string_view, num>{enum_name<static_cast<T>(Is)>()...};
    }(std::make_index_sequence<num>{});
    return names[static_cast<std::size_t>(value)];
}

protected:
  int _t = 0;
};

TEST_F(EnumTest, TestBasic) {
    using namespace std;
    Color color = Color::RED;
    std::cout << color << std::endl;

    print_fn<Color::RED>();
    std::cout << enum_name(color) << std::endl;
}
