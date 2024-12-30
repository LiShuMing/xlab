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
#include <memory>
#include <ranges>
#include <numeric> 
#include <algorithm> // new fold_left, ends_with


#include "absl/container/flat_hash_set.h"
#include "absl/container/flat_hash_map.h"
#include "absl/container/node_hash_map.h"

using namespace std;

namespace test {

// Basic Test
class RangesTest : public testing::Test {};

using namespace std;

TEST_F(RangesTest, Basic1) {

    {
        std::vector<int> numbers = {1, 2, 3, 4, 5};

        // auto sum = std::ranges::fold_left(numbers, 0, [](int acc, int n) { return acc + n; });
        // std::println("Sum of numbers: {}", sum);
    }
    // auto vec1 = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10};
    // auto sum1 = ranges::fold_left(vec1, 0, std::plus<int>());
    // cout << "sum1=" << sum1 << endl;

    // auto sum2 = std::accumulate(vec1, 0);
    // cout << "sum2=" << sum2 << endl;

    // bool is_all_even = ranges::all_of(vec1, [](int i) { return i % 2 == 0; });
    // cout << "is_all_even=" << is_all_even << endl;

    // bool is_contains_four = ranges::any_of(vec1, [](int i) { return i == 4; });
    // cout << "is_contains_four=" << is_contains_four << endl;
}

} // namespace test
