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
#include <cstdlib>
#include <ctime>
#include <iomanip>
#include <iostream>
#include <sstream>


#include "common/skiplist/skiplist_v2.h"

class SkipListV2Test : public testing::Test {};

TEST_F(SkipListV2Test, TestClockResolution) {
    // Declare with any type that has sane comparison.
    SkipList<double, double> sl(4);

    sl.insert_element(42.0, 1.0);
    sl.insert_element(21.0, 2.0);
    sl.insert_element(84.0, 3.0);
    GTEST_ASSERT_TRUE(sl.search_element(42.0));
    sl.display_list();

    GTEST_ASSERT_EQ(sl.size(), 3);
    sl.delete_element(21.0); // throws OrderedStructs::SkipList::ValueError if value not present
    sl.display_list();
    GTEST_ASSERT_FALSE(sl.search_element(21.0));
    GTEST_ASSERT_EQ(sl.size(), 2);
}
