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

#include "common/btree/bplustree.h"

using namespace std;

namespace test {

// Basic Test
class BPlusPlusTreeTest: public testing::Test {};

TEST_F(BPlusPlusTreeTest, TestBasic) {
    char* filename = "./bplusplus.out";
    {
        struct bplus_tree *tree = bplus_tree_init(filename, 1024);
        GTEST_ASSERT_TRUE(tree != nullptr);
        bplus_tree_put(tree, 1, 1);
        bplus_tree_put(tree, 2, 1);
        bplus_tree_put(tree, 3, 1);
        GTEST_ASSERT_EQ(bplus_tree_get(tree, 1), 1);
        GTEST_ASSERT_EQ(bplus_tree_get(tree, 2), 1);
        GTEST_ASSERT_EQ(bplus_tree_get(tree, 3), 1);

        int ans = bplus_tree_get_range(tree, 1, 3);
        GTEST_ASSERT_EQ(ans, 1);
        bplus_tree_deinit(tree);
    }

    {
        // struct bplus_tree *tree = bplus_tree_init(filename, 1024);
        // GTEST_ASSERT_TRUE(tree != nullptr);
        // GTEST_ASSERT_EQ(bplus_tree_get(tree, 1), 1);
        // GTEST_ASSERT_EQ(bplus_tree_get(tree, 2), 1);
        // GTEST_ASSERT_EQ(bplus_tree_get(tree, 3), 1);

        // int ans = bplus_tree_get_range(tree, 1, 3);
        // GTEST_ASSERT_EQ(ans, 1);
        // bplus_tree_deinit(tree);
    }
}

} // namespace test
