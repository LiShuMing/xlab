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

using namespace std;

namespace test {

// Basic Test
class AtomicTest : public testing::Test {};

using namespace std;

TEST_F(AtomicTest, Basic1) {
    {
        atomic<int> a(0);
        atomic<long long> b(0);
        cout << " a=" << a << " b=" << b << endl;
        cout << "atomic<int> is lock free: " << atomic_is_lock_free(&a) << endl;
        cout << "atomic<long> is lock free: " << atomic_is_lock_free(&b) << endl;
    }
    {
        std::cout << "std::atomic<size_t> is lock-free: " << std::atomic<size_t>().is_lock_free()
                  << std::endl;

        // 测试 shared_ptr 操作
        auto ptr1 = std::make_shared<int>(42);
        auto ptr2 = ptr1;

        cout << "shared_ptr is lock free: " << atomic_is_lock_free(&ptr1) << endl;

        // shared_ptr 引用计数的递增和递减
        std::cout << "Use count after copy: " << ptr1.use_count() << std::endl;
        ptr2.reset();
        std::cout << "Use count after reset: " << ptr1.use_count() << std::endl;
    }
}
TEST_F(AtomicTest, Basic2){
    {

        std::atomic<int> atomic_var(42);
        int expected = 42; // 当前值的预期
        int desired = 100; // 新值

        // 使用 weak 进行循环重试
        while (!atomic_var.compare_exchange_weak(expected, desired)) {
            std::cout << "Weak failed, retrying... expected: " << expected << std::endl;
            // expected 会被更新为当前的实际值
        }
    }
}

class Base {
  public:
    virtual ~Base() = default;
    virtual void foo() { std::cout << "Base foo\n"; }
};

class Derived : public Base {
  public:
    void foo() override { std::cout << "Derived foo\n"; }
};

TEST_F(AtomicTest, TestStaticPointerCast) {
    std::shared_ptr<Base> basePtr = std::make_shared<Derived>();
    ASSERT_EQ(basePtr.use_count(), 1);
    {
        std::shared_ptr<Derived> derivedPtr = std::static_pointer_cast<Derived>(basePtr);
        ASSERT_EQ(basePtr.use_count(), 2);
        ASSERT_EQ(derivedPtr.use_count(), 2);
    }
    {
        std::shared_ptr<Derived> derivedPtr = std::static_pointer_cast<Derived>(std::move(basePtr));
        ASSERT_EQ(basePtr.use_count(), 0);
        ASSERT_EQ(derivedPtr.use_count(), 1);
    }
}

} // namespace test
