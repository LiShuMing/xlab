#include <gtest/gtest.h>

#include <atomic>
#include <cstring>
#include <functional>
#include <iostream>
#include <list>
#include <map>
#include <queue>
#include <shared_mutex>
#include <string>
#include <vector>

#include "utils/defer.h"

using namespace std;

namespace test {

// Basic Test
class DeferTest : public testing::Test {};

TEST_F(DeferTest, Test1) {
    int *foo = NULL;
    int *bar = new int(10);
    xlab::Defer x([&foo, &bar]() {
        if (foo != NULL) {
            delete foo;
        }
        if (bar != NULL) {
            delete bar;
        }
    });

    // if (true) { return; } // return under some condition
    if (true) {
        foo = new int(20);
    } // malloc under some condition
    if (true) {
        delete bar;
        bar = NULL;
    } // even free under some condition...

    // ensure foo and bar are deleted

    // some op...
    return;
}

} // namespace test

int main(int argc, char **argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
