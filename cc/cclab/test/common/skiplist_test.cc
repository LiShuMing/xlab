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


#include "common/skiplist/SkipList.h"

class SkipListTest : public testing::Test {};

TEST_F(SkipListTest, TestClockResolution) {
    int count = 10;
    double average_ticks = 0;
    for (int i = 0; i < count; ++i) {
        clock_t start = clock();
        while (clock() == start) {
        }
        clock_t diff = clock() - start;
        average_ticks += diff;
    }
    std::cout << "Average ticks (" << count;
    std::cout << " tests) for change in clock(): " << average_ticks / count;
    std::cout << " which is every " << average_ticks / count / CLOCKS_PER_SEC;
    std::cout << " (s)" << std::endl;
    std::cout << "CLOCKS_PER_SEC: " << CLOCKS_PER_SEC << std::endl;
}


TEST_F(SkipListTest, TestBasic) {
    // Declare with any type that has sane comparison.
    OrderedStructs::SkipList::HeadNode<double> sl;

    sl.insert(42.0);
    sl.insert(21.0);
    sl.insert(84.0);
    GTEST_ASSERT_TRUE(sl.has(42.0));
    GTEST_ASSERT_EQ(sl.size(), 3);
    // throws OrderedStructs::SkipList::IndexError if index out of range
    GTEST_ASSERT_EQ(sl.at(1), 42.0);
    sl.remove(21.0); // throws OrderedStructs::SkipList::ValueError if value not present
    GTEST_ASSERT_EQ(sl.size(), 2);
    GTEST_ASSERT_EQ(sl.at(1), 84.0);
}

int main(int argc, char** argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}