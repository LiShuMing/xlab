#include <gtest/gtest.h>

#include <atomic>
#include <cstring>
#include <functional>
#include <iostream>
#include <list>
#include <map>
#include <queue>
#include <string>
#include <shared_mutex>
#include <vector>

#include <iostream>
#include <memory>
#include <cstdio>
#include <string_view>
#include "utils/foo.h"

using namespace std;

namespace test {

// Basic Test
class StringTest : public testing::Test {};

TEST_F(StringTest, Test1) {
    std::string test_hex = "ac10";
    auto str_size = test_hex.size();
    if (str_size % 2 != 0) {
        //
        return;
    }
    // trim padding

    // compute size
    for (int i = 0; i < str_size; i += 2) {
    }
}

void print_me(std::string_view s) {
    printf("%s\n", s.data());
}

TEST_F(StringTest, TestStringView) {
    char next[] = {'n','e','x','t'};
    char hello[] = {'H','e','l','l','o', ' ', 'W','o','r','l','d'};
    std::string_view sub(hello, 5);
    std::cout << sub << "\n";
    print_me(sub);
}


} // namespace test