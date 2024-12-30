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

#include "utils/default_init_default.h"
#include "utils/foo.h"

using namespace std;

namespace test {

struct X {
    int x_;
    X() { std::cout << "default constructor\n"; }
    X(int x) {
        x_ = x;
        std::cout << "default constructor:" << x << std::endl;
    }

    X(const X &) { std::cout << "copy constructor\n"; }

    ~X() { std::cout << "deconstructor:" << x_ << std::endl; }

    void print() { cout << " print :" << x_ << endl; }
};

struct A1 {
    A1() { printf("A1 ctror"); }
    virtual ~A1() { printf("A1 dtor\n"); }
};
struct A2 : A1 {
    virtual ~A2() { printf("A2 dtor\n"); }
};
struct A3 : A2 {
    virtual ~A3() { printf("A3 dtor\n"); }
};

struct B1 {
    B1() { printf("B1 ctor\n"); }
    B1(const B1 &b) { printf("B1 copy\n"); }
    ~B1() { printf("B1 dtor\n"); }
};
struct B2 : B1 {
    B2() { printf("B2 ctro\n"); }
    B2(const B2 &b) { printf("B2 copy\n"); }
    ~B2() { printf("B2 dtor\n"); }
};
struct B3 : B2 {
    B3() { printf("B3 ctror\n"); }
    B3(const B3 &b) { printf("B3 copy\n"); }
    ~B3() { printf("B3 dtor\n"); }
};

struct StructRef {
    const B1 &b1;
    const B2 &b2;
    int a{1};
};

struct StructNonRef {
    B1 b1;
    B2 b2;
    int a{1};
};

// Basic Test
class BasicTest : public testing::Test {};

TEST_F(BasicTest, assertion) {
    ASSERT_EQ(1, 1);
    ASSERT_TRUE(true);
    GTEST_LOG_(INFO) << "ok";
}

TEST_F(BasicTest, foobar) {
    ASSERT_EQ(detail::add(1, 2), 3);
    GTEST_LOG_(INFO) << "1+2=" << detail::add(1, 2);
}

TEST_F(BasicTest, atomic) {
    std::atomic<void *> a(nullptr);
    void *b = a;
    a.compare_exchange_strong(b, (void *)20);
}

TEST_F(BasicTest, test2) {
    X x;
    X x1(1);
    x1.print();
    auto func = [&x]() { x.print(); };
    func();
}

TEST_F(BasicTest, test3) {
    A1 *a = new A3;
    delete a;
    printf("\n");

    B1 *b = new B3;
    delete b;
    printf("\n");

    B3 *b2 = new B3;
    delete b2;
}

TEST_F(BasicTest, test4) {
    std::vector<int> alice{1, 2, 3};
    std::vector<int> bob{7, 8, 9, 10};
    std::vector<int> eve{1, 2, 3};

    std::cout << std::boolalpha;

    // Compare non equal containers
    std::cout << "alice == bob returns " << (alice == bob) << '\n';
    std::cout << "alice != bob returns " << (alice != bob) << '\n';
    std::cout << "alice <  bob returns " << (alice < bob) << '\n';
    std::cout << "alice <= bob returns " << (alice <= bob) << '\n';
    std::cout << "alice >  bob returns " << (alice > bob) << '\n';
    std::cout << "alice >= bob returns " << (alice >= bob) << '\n';

    std::cout << '\n';

    // Compare equal containers
    std::cout << "alice == eve returns " << (alice == eve) << '\n';
    std::cout << "alice != eve returns " << (alice != eve) << '\n';
    std::cout << "alice <  eve returns " << (alice < eve) << '\n';
    std::cout << "alice <= eve returns " << (alice <= eve) << '\n';
    std::cout << "alice >  eve returns " << (alice > eve) << '\n';
    std::cout << "alice >= eve returns " << (alice >= eve) << '\n';
}

TEST_F(BasicTest, TestQueue) {
    priority_queue<int, vector<int>, greater<int>> que;
    for (int i = 10; i > 0; i--) {
        que.push(i);
    }
    int sz = que.size();
    while (!que.empty()) {
        int val = que.top();
        cout << "val:" << val << endl;
        que.pop();
    }
    vector<int> va;
    va.push_back(1);
    va.clear();
    va.clear();
}

TEST_F(BasicTest, TestStructRef) {
    {
        cout << "start ref" << endl;
        B1 b1;
        B2 b2;
        printf("struct ref\n");
        StructRef ref{.b1 = b1, .b2 = b2};
    }
    {
        cout << "start non ref" << endl;
        B1 b1;
        B2 b2;
        printf("struct non ref\n");
        StructNonRef nonref{.b1 = b1, .b2 = b2};
    }
}

TEST_F(BasicTest, TestString1) {
    int ret = std::strcmp("a ", "a    ");
    std::cout << "ret :" << ret << std::endl;
    ASSERT_EQ(ret, -1);
}

/**
 * ==13663==ERROR: AddressSanitizer: heap-use-after-free on address 0x5020000016f0 at pc 0x562f28210c4a bp 0x7fffffd58f30 sp 0x7fffffd58f28
READ of size 4 at 0x5020000016f0 thread T0
    #0 0x562f28210c49 in test::BasicTest_TestSharedPtr1_Test::TestBody() /root/work/xlab/cc/cclab/test/common/basic_test.cc:191:30
    #1 0x7f2706ccaba0 in void testing::internal::HandleSehExceptionsInMethodIfSupported<testing::Test, void>(testing::Test*, void (testing::Test::*)(), char const*) /root/work/xlab/cc/thirdparty/googletest/googletest/src/gtest.cc:2638:10
    #2 0x7f2706ccaba0 in void testing::internal::HandleExceptionsInMethodIfSupported<testing::Test, void>(testing::Test*, void (testing::Test::*)(), char const*) /root/work/xlab/cc/thirdparty/googletest/googletest/src/gtest.cc:2674:14
    #3 0x7f2706c709f8 in testing::Test::Run() /root/work/xlab/cc/thirdparty/googletest/googletest/src/gtest.cc:2713:5
    #4 0x7f2706c74f9f in testing::TestInfo::Run() /root/work/xlab/cc/thirdparty/googletest/googletest/src/gtest.cc:2859:11
    #5 0x7f2706c77cc4 in testing::TestSuite::Run() /root/work/xlab/cc/thirdparty/googletest/googletest/src/gtest.cc:3037:30
    #6 0x7f2706cae5fa in testing::internal::UnitTestImpl::RunAllTests() /root/work/xlab/cc/thirdparty/googletest/googletest/src/gtest.cc:5967:44
    #7 0x7f2706ccd9d0 in bool testing::internal::HandleSehExceptionsInMethodIfSupported<testing::internal::UnitTestImpl, bool>(testing::internal::UnitTestImpl*, bool (testing::internal::UnitTestImpl::*)(), char const*) /root/work/xlab/cc/thirdparty/googletest/googletest/src/gtest.cc:2638:10
    #8 0x7f2706ccd9d0 in bool testing::internal::HandleExceptionsInMethodIfSupported<testing::internal::UnitTestImpl, bool>(testing::internal::UnitTestImpl*, bool (testing::internal::UnitTestImpl::*)(), char const*) /root/work/xlab/cc/thirdparty/googletest/googletest/src/gtest.cc:2674:14
    #9 0x7f2706cad94a in testing::UnitTest::Run() /root/work/xlab/cc/thirdparty/googletest/googletest/src/gtest.cc:5546:10
    #10 0x562f281eea70 in RUN_ALL_TESTS() /root/work/xlab/cc/thirdparty/googletest/googletest/include/gtest/gtest.h:2334:73
    #11 0x562f281edbde in main /root/work/xlab/cc/cclab/test/common/abseil_test.cc:43:12
    #12 0x7f27063afd8f  (/lib/x86_64-linux-gnu/libc.so.6+0x29d8f) (BuildId: 490fef8403240c91833978d494d39e537409b92e)
    #13 0x7f27063afe3f in __libc_start_main (/lib/x86_64-linux-gnu/libc.so.6+0x29e3f) (BuildId: 490fef8403240c91833978d494d39e537409b92e)
    #14 0x562f2810b394 in _start (/root/work/xlab/cc/cclab/build_ASAN/test/common/common_test+0x67394) (BuildId: 475a7a8d84e053a9093431b58fab177e45334614)

0x5020000016f0 is located 0 bytes inside of 4-byte region [0x5020000016f0,0x5020000016f4)
freed by thread T0 here:
    #0 0x562f281eb792 in operator delete(void*, unsigned long) (/root/work/xlab/cc/cclab/build_ASAN/test/common/common_test+0x147792) (BuildId: 475a7a8d84e053a9093431b58fab177e45334614)
    #1 0x562f28220a4c in std::_Sp_counted_ptr<int*, (__gnu_cxx::_Lock_policy)2>::_M_dispose() /usr/lib/gcc/x86_64-linux-gnu/11/../../../../include/c++/11/bits/shared_ptr_base.h:348:9
    #2 0x562f2820c499 in std::_Sp_counted_base<(__gnu_cxx::_Lock_policy)2>::_M_release() /usr/lib/gcc/x86_64-linux-gnu/11/../../../../include/c++/11/bits/shared_ptr_base.h:168:6
    #3 0x562f2820c269 in std::__shared_count<(__gnu_cxx::_Lock_policy)2>::~__shared_count() /usr/lib/gcc/x86_64-linux-gnu/11/../../../../include/c++/11/bits/shared_ptr_base.h:705:11
    #4 0x562f2820dc38 in std::__shared_ptr<int, (__gnu_cxx::_Lock_policy)2>::~__shared_ptr() /usr/lib/gcc/x86_64-linux-gnu/11/../../../../include/c++/11/bits/shared_ptr_base.h:1154:31
    #5 0x562f2820bc24 in std::shared_ptr<int>::~shared_ptr() /usr/lib/gcc/x86_64-linux-gnu/11/../../../../include/c++/11/bits/shared_ptr.h:122:11
    #6 0x562f28210bf0 in test::BasicTest_TestSharedPtr1_Test::TestBody() /root/work/xlab/cc/cclab/test/common/basic_test.cc:188:5
    #7 0x7f2706ccaba0 in void testing::internal::HandleSehExceptionsInMethodIfSupported<testing::Test, void>(testing::Test*, void (testing::Test::*)(), char const*) /root/work/xlab/cc/thirdparty/googletest/googletest/src/gtest.cc:2638:10
    #8 0x7f2706ccaba0 in void testing::internal::HandleExceptionsInMethodIfSupported<testing::Test, void>(testing::Test*, void (testing::Test::*)(), char const*) /root/work/xlab/cc/thirdparty/googletest/googletest/src/gtest.cc:2674:14
    #9 0x7f2706c709f8 in testing::Test::Run() /root/work/xlab/cc/thirdparty/googletest/googletest/src/gtest.cc:2713:5
    #10 0x7f2706c74f9f in testing::TestInfo::Run() /root/work/xlab/cc/thirdparty/googletest/googletest/src/gtest.cc:2859:11
    #11 0x7f2706c77cc4 in testing::TestSuite::Run() /root/work/xlab/cc/thirdparty/googletest/googletest/src/gtest.cc:3037:30
    #12 0x7f2706cae5fa in testing::internal::UnitTestImpl::RunAllTests() /root/work/xlab/cc/thirdparty/googletest/googletest/src/gtest.cc:5967:44
    #13 0x7f2706ccd9d0 in bool testing::internal::HandleSehExceptionsInMethodIfSupported<testing::internal::UnitTestImpl, bool>(testing::internal::UnitTestImpl*, bool (testing::internal::UnitTestImpl::*)(), char const*) /root/work/xlab/cc/thirdparty/googletest/googletest/src/gtest.cc:2638:10
    #14 0x7f2706ccd9d0 in bool testing::internal::HandleExceptionsInMethodIfSupported<testing::internal::UnitTestImpl, bool>(testing::internal::UnitTestImpl*, bool (testing::internal::UnitTestImpl::*)(), char const*) /root/work/xlab/cc/thirdparty/googletest/googletest/src/gtest.cc:2674:14
    #15 0x7f2706cad94a in testing::UnitTest::Run() /root/work/xlab/cc/thirdparty/googletest/googletest/src/gtest.cc:5546:10
    #16 0x562f281eea70 in RUN_ALL_TESTS() /root/work/xlab/cc/thirdparty/googletest/googletest/include/gtest/gtest.h:2334:73
    #17 0x562f281edbde in main /root/work/xlab/cc/cclab/test/common/abseil_test.cc:43:12
    #18 0x7f27063afd8f  (/lib/x86_64-linux-gnu/libc.so.6+0x29d8f) (BuildId: 490fef8403240c91833978d494d39e537409b92e)

previously allocated by thread T0 here:
    #0 0x562f281eab2d in operator new(unsigned long) (/root/work/xlab/cc/cclab/build_ASAN/test/common/common_test+0x146b2d) (BuildId: 475a7a8d84e053a9093431b58fab177e45334614)
    #1 0x562f28210b11 in test::BasicTest_TestSharedPtr1_Test::TestBody() /root/work/xlab/cc/cclab/test/common/basic_test.cc:183:14
    #2 0x7f2706ccaba0 in void testing::internal::HandleSehExceptionsInMethodIfSupported<testing::Test, void>(testing::Test*, void (testing::Test::*)(), char const*) /root/work/xlab/cc/thirdparty/googletest/googletest/src/gtest.cc:2638:10
    #3 0x7f2706ccaba0 in void testing::internal::HandleExceptionsInMethodIfSupported<testing::Test, void>(testing::Test*, void (testing::Test::*)(), char const*) /root/work/xlab/cc/thirdparty/googletest/googletest/src/gtest.cc:2674:14
    #4 0x7f2706c709f8 in testing::Test::Run() /root/work/xlab/cc/thirdparty/googletest/googletest/src/gtest.cc:2713:5
    #5 0x7f2706c74f9f in testing::TestInfo::Run() /root/work/xlab/cc/thirdparty/googletest/googletest/src/gtest.cc:2859:11
    #6 0x7f2706c77cc4 in testing::TestSuite::Run() /root/work/xlab/cc/thirdparty/googletest/googletest/src/gtest.cc:3037:30
    #7 0x7f2706cae5fa in testing::internal::UnitTestImpl::RunAllTests() /root/work/xlab/cc/thirdparty/googletest/googletest/src/gtest.cc:5967:44
    #8 0x7f2706ccd9d0 in bool testing::internal::HandleSehExceptionsInMethodIfSupported<testing::internal::UnitTestImpl, bool>(testing::internal::UnitTestImpl*, bool (testing::internal::UnitTestImpl::*)(), char const*) /root/work/xlab/cc/thirdparty/googletest/googletest/src/gtest.cc:2638:10
    #9 0x7f2706ccd9d0 in bool testing::internal::HandleExceptionsInMethodIfSupported<testing::internal::UnitTestImpl, bool>(testing::internal::UnitTestImpl*, bool (testing::internal::UnitTestImpl::*)(), char const*) /root/work/xlab/cc/thirdparty/googletest/googletest/src/gtest.cc:2674:14
    #10 0x7f2706cad94a in testing::UnitTest::Run() /root/work/xlab/cc/thirdparty/googletest/googletest/src/gtest.cc:5546:10
    #11 0x562f281eea70 in RUN_ALL_TESTS() /root/work/xlab/cc/thirdparty/googletest/googletest/include/gtest/gtest.h:2334:73
    #12 0x562f281edbde in main /root/work/xlab/cc/cclab/test/common/abseil_test.cc:43:12
    #13 0x7f27063afd8f  (/lib/x86_64-linux-gnu/libc.so.6+0x29d8f) (BuildId: 490fef8403240c91833978d494d39e537409b92e)

 */
TEST_F(BasicTest, TestSharedPtr1) {
    int *a = new int(1);
    {
        shared_ptr<int> a_ptr(a);
        std::cout << "shared ptr a:" << *a_ptr << std::endl;
        // pointer a is destructor here!!!
    }

    // WRONG VALUE!
    // dangerous!!! a is already deleted
    // heap use after free
    //std::cout << "ptr a:" << *a << std::endl;
}

TEST_F(BasicTest, TestUniquePtr) {
    std::unique_ptr<int> u_a1;
    if (u_a1) {
        std::cout << "u_a1 is not empty" << std::endl;
        ;
    } else {
        std::cout << "u_a1 is empty" << std::endl;
        ;
    }
}

class V1 {
  public:
    V1(std::vector<int> a) : _a(std::move(a)) {}
    const std::vector<int> &a() const { return _a; }

  private:
    std::vector<int> _a;
};

class V2 {
  public:
    V2(std::vector<int> &&a) : _a(std::move(a)) {}
    const std::vector<int> &a() const { return _a; }

  private:
    std::vector<int> _a;
};

TEST_F(BasicTest, TestMove) {
    {
        std::cout << "V1" << std::endl;
        std::vector<int> data;
        data.push_back(1);
        V1 v(data);
        std::cout << "v1's data size:" << v.a().size() << ", data's size:" << data.size()
                  << std::endl;
    }
    {
        std::cout << "V1" << std::endl;
        std::vector<int> data;
        data.push_back(1);
        V2 v(std::move(data));
        std::cout << "v1's data size:" << v.a().size() << ", data's size:" << data.size()
                  << std::endl;
    }
}

TEST_F(BasicTest, TestSharedLock1) {
    std::shared_mutex sm;
    {
        cout << "case 1" << endl;
        std::unique_lock<std::shared_mutex> l1(sm);

        // BAD!!!
        // std::shared_lock<std::shared_mutex> l2(sm);
        cout << "case 1 done" << endl;
    }
    {
        cout << "case 2" << endl;
        std::unique_lock<std::shared_mutex> l1(sm);
        // BAD!!
        // std::unique_lock<std::shared_mutex> l2(sm);
        cout << "case 2 done" << endl;
    }
    {
        cout << "case 3" << endl;
        std::shared_lock<std::shared_mutex> l1(sm);
        std::shared_lock<std::shared_mutex> l2(sm);
        cout << "case 3 done" << endl;
    }
}

TEST_F(BasicTest, TestSharedLock2) {
    // std::shared_mutex sm;
    // auto func1 = [=]() {
    //     cout << "case 1" << endl;
    //     std::unique_lock<std::shared_mutex> l1(sm);
    //     std::shared_lock<std::shared_mutex> l2(sm);
    //     cout << "case 1 done" << endl;
    // };
    // {
    //     cout << "case 2" << endl;
    //     std::unique_lock<std::shared_mutex> l1(sm);
    //     std::unique_lock<std::shared_mutex> l2(sm);
    //     cout << "case 2 done" << endl;
    // }
}

TEST_F(BasicTest, TestAtomic) {
    std::atomic<int32_t> a1 = 0;
    auto t1 = a1.fetch_add(1);
    cout << "t1:" << t1 << ", a1=" << a1 << endl;
    auto t2 = a1.fetch_add(1) + 1;
    cout << "t2:" << t2 << ", a1=" << a1 << endl;
}

void print_container(const std::list<int> &c) {
    for (int i : c)
        std::cout << i << " ";
    std::cout << '\n';
}

TEST_F(BasicTest, TestList) {
    std::list<int> c{0, 1, 2, 3, 4, 5, 6, 7, 8, 9};
    print_container(c);
    // for (std::list<int>::iterator it = c.begin(); it != c.end();) {
    std::list<int>::iterator it = c.begin();
    while (it != c.end()) {
        if (*it % 2 == 0) {
            it = c.erase(it);
        }
        ++it;
    }
    print_container(c);
}

TEST_F(BasicTest, TestVector_CopyBack) {
    std::vector<std::string> a1{"a", "b", "c"};
    std::vector<std::string> a2;
    a2.resize(a1.size() - 1);
    std::copy_backward(a1.begin() + 1, a1.end(), a2.end());
    for (auto &a : a2) {
        std::cout << "a:" << a << "\n";
    }

    // !!!
    a2.resize(0);
}

TEST_F(BasicTest, TestAllocator1) {
    {
        std::vector<int32_t> vec;
        vec.resize(10);
        for (auto &v : vec) {
            std::cout << v << " ";
        }
        std::cout << std::endl;
    }
    {
        raw::raw_vector<int32_t> vec;
        vec.resize(10);
        for (auto &v : vec) {
            std::cout << v << " ";
        }
        std::cout << std::endl;
    }
}

TEST_F(BasicTest, TestAllocator2) {
    {
        std::vector<int32_t> vec;
        vec.resize(10, 1);
        for (auto &v : vec) {
            std::cout << v << " ";
        }
        std::cout << std::endl;
    }
    {
        raw::raw_vector<int32_t> vec;
        vec.resize(10, 1);
        for (auto &v : vec) {
            std::cout << v << " ";
        }
        std::cout << std::endl;
    }
}

} // namespace test
