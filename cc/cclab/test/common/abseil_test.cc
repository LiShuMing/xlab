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

#include "absl/container/flat_hash_set.h"
#include "absl/container/flat_hash_map.h"
#include "absl/container/node_hash_map.h"
#include "absl/strings/str_join.h"

using namespace std;

namespace test {

// Basic Test
class AbseilTest : public testing::Test {};

TEST_F(AbseilTest, FlatHashMap1) {
    absl::flat_hash_set<std::string> set1;
    set1.insert("a");
    set1.insert("a");
    set1.insert("b");

    absl::flat_hash_map<int, std::string> map1;
    map1.insert({1, "a"});
    auto iter = map1.find(1);
    ASSERT_TRUE(iter != map1.end());
    std::cout << "result: " << iter->second;
    ASSERT_EQ(iter->second, "a");
}

TEST_F(AbseilTest, String) {
    auto strs = {"a", "b", "c"};
    auto result = absl::StrJoin(strs, ",");
    ASSERT_EQ(result, "a,b,c");
    // LOG(INFO) << "result: " << result;
}
} // namespace test

int main(int argc, char** argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
