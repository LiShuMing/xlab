#include <gtest/gtest.h>

#include <atomic>

#include "utils/foo.h"

namespace test {

class GTestDemo : public testing::Test {};

TEST_F(GTestDemo, assertion) {
    ASSERT_EQ(1, 1);
    ASSERT_TRUE(true);
    GTEST_LOG_(INFO) << "ok";
}

TEST_F(GTestDemo, foobar) {
    ASSERT_EQ(detail::add(1, 2), 3);
    GTEST_LOG_(INFO) << "1+2=" << detail::add(1, 2);
}

TEST_F(GTestDemo, atomic) {
    std::atomic<void*> a(nullptr);
    void* b = a;
    a.compare_exchange_strong(b, (void*)20);
}

} // namespace test
