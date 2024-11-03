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

#include "common/btree/btree.h"
#include "common/btree/set.h"
#include "common/btree/map.h"

using namespace std;

namespace test {

// Basic Test
class BTreeTest: public testing::Test {};

TEST_F(BTreeTest, TestSet) {
    btree::set<int32_t> s;
    for (int i = 0; i < 10; i++) {
        s.insert(i);
        s.insert(i);
    }
    GTEST_ASSERT_EQ(s.size(), 10);
    for (int i = 0; i < 10; i++) {
        GTEST_ASSERT_EQ(s.count(i), 1);
    }
}

TEST_F(BTreeTest, TestMap) {
    btree::map<int32_t, int32_t> s;
    for (int i = 0; i < 10; i++) {
        s.emplace(i, i);
        s.emplace(i, i);
    }
    GTEST_ASSERT_EQ(s.size(), 10);
    for (int i = 0; i < 10; i++) {
        GTEST_ASSERT_EQ(s[i], i);
    }
}
} // namespace test

int main(int argc, char** argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
