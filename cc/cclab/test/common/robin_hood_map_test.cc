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

#include "utils/foo.h"

#include "common/robin_hood_map.h"

using namespace std;

// Basic Test
class RobinHoodMapTest : public testing::Test {};

TEST_F(RobinHoodMapTest, assertion) {
    robin_hood::unordered_flat_set<int32_t> a;
    a.insert(1);
    a.insert(2);
    a.insert(3);

    cout << "a.size() = " << a.size() << endl;
    EXPECT_EQ(a.size(), 3);
}
