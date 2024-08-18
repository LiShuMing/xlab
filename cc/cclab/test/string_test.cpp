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

#include "foo.h"

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
    for (size i = 0; i < str_size; i += 2) {
    }
}


} // namespace test

int main(int argc, char** argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
