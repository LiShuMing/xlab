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

#include "utils/env_var.h"

using namespace std;

namespace test {

class EnvVarTest : public testing::Test {};

TEST_F(EnvVarTest, Test1) {
    std::string v;
    bool succ = xlab::EnvVar::getenv("HOME", &v);
    GTEST_ASSERT_TRUE(succ);
    std::cout << succ << "," << v << std::endl;
    std::string k = std::string("xlab_EnvVar_test_k_") + std::to_string(std::time(0));
    succ = xlab::EnvVar::getenv(k, &v);
    GTEST_ASSERT_FALSE(succ);

    succ = xlab::EnvVar::unsetenv(k);
    GTEST_ASSERT_TRUE(succ);

    succ = xlab::EnvVar::setenv(k, "111");
    GTEST_ASSERT_TRUE(succ);
    succ = xlab::EnvVar::getenv(k, &v);
    GTEST_ASSERT_TRUE(succ);
    GTEST_ASSERT_EQ(v, "111");

    succ = xlab::EnvVar::unsetenv(k);
    GTEST_ASSERT_TRUE(succ);
    succ = xlab::EnvVar::getenv(k, &v);
    GTEST_ASSERT_FALSE(succ);
    return;
}

} // namespace test

int main(int argc, char **argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
