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

#include <iostream>
#include <memory>
#include <cstdio>
#include <string_view>
#include "utils/foo.h"

using namespace std;

namespace test {

// Basic Test
class StringTest : public testing::Test {};

TEST_F(StringTest, Test1) {
    std::string test_hex = "ac10";
    auto str_size = test_hex.size();
    if (str_size % 2 != 0) {
        //
        return;
    }
    // trim padding

    // compute size
    for (int i = 0; i < str_size; i += 2) {
    }
}

void print_me(std::string_view s) {
    printf("%s\n", s.data());
}

/**
 * ==14412==ERROR: AddressSanitizer: stack-buffer-overflow on address 0x7feea462632b at pc 0x5632c66262d7 bp 0x7ffc0b412dd0 sp 0x7ffc0b412558
READ of size 12 at 0x7feea462632b thread T0
    #0 0x5632c66262d6 in printf_common(void*, char const*, __va_list_tag*) asan_interceptors.cpp.o
    #1 0x5632c6627f0d in printf (/root/work/xlab/cc/cclab/build_ASAN/test/common/common_test+0x8ef0d) (BuildId: 701a4a2915f2955b0f55194896fb996bae90a143)
    #2 0x5632c6779d77 in test::print_me(std::basic_string_view<char, std::char_traits<char>>) /root/work/xlab/cc/cclab/test/common/string_test.cc:42:5
    #3 0x5632c6779f36 in test::StringTest_TestStringView_Test::TestBody() /root/work/xlab/cc/cclab/test/common/string_test.cc:50:5
    #4 0x7feea6ca3ba0 in void testing::internal::HandleSehExceptionsInMethodIfSupported<testing::Test, void>(testing::Test*, void (testing::Test::*)(), char const*) /root/work/xlab/cc/thirdparty/googletest/googletest/src/gtest.cc:2638:10
    #5 0x7feea6ca3ba0 in void testing::internal::HandleExceptionsInMethodIfSupported<testing::Test, void>(testing::Test*, void (testing::Test::*)(), char const*) /root/work/xlab/cc/thirdparty/googletest/googletest/src/gtest.cc:2674:14
    #6 0x7feea6c499f8 in testing::Test::Run() /root/work/xlab/cc/thirdparty/googletest/googletest/src/gtest.cc:2713:5
    #7 0x7feea6c4df9f in testing::TestInfo::Run() /root/work/xlab/cc/thirdparty/googletest/googletest/src/gtest.cc:2859:11
    #8 0x7feea6c50cc4 in testing::TestSuite::Run() /root/work/xlab/cc/thirdparty/googletest/googletest/src/gtest.cc:3037:30
    #9 0x7feea6c875fa in testing::internal::UnitTestImpl::RunAllTests() /root/work/xlab/cc/thirdparty/googletest/googletest/src/gtest.cc:5967:44
    #10 0x7feea6ca69d0 in bool testing::internal::HandleSehExceptionsInMethodIfSupported<testing::internal::UnitTestImpl, bool>(testing::internal::UnitTestImpl*, bool (testing::internal::UnitTestImpl::*)(), char const*) /root/work/xlab/cc/thirdparty/googletest/googletest/src/gtest.cc:2638:10
    #11 0x7feea6ca69d0 in bool testing::internal::HandleExceptionsInMethodIfSupported<testing::internal::UnitTestImpl, bool>(testing::internal::UnitTestImpl*, bool (testing::internal::UnitTestImpl::*)(), char const*) /root/work/xlab/cc/thirdparty/googletest/googletest/src/gtest.cc:2674:14
    #12 0x7feea6c8694a in testing::UnitTest::Run() /root/work/xlab/cc/thirdparty/googletest/googletest/src/gtest.cc:5546:10
    #13 0x5632c66e3a70 in RUN_ALL_TESTS() /root/work/xlab/cc/thirdparty/googletest/googletest/include/gtest/gtest.h:2334:73
    #14 0x5632c66e2bde in main /root/work/xlab/cc/cclab/test/common/abseil_test.cc:43:12
    #15 0x7feea6388d8f  (/lib/x86_64-linux-gnu/libc.so.6+0x29d8f) (BuildId: 490fef8403240c91833978d494d39e537409b92e)
    #16 0x7feea6388e3f in __libc_start_main (/lib/x86_64-linux-gnu/libc.so.6+0x29e3f) (BuildId: 490fef8403240c91833978d494d39e537409b92e)
    #17 0x5632c6600394 in _start (/root/work/xlab/cc/cclab/build_ASAN/test/common/common_test+0x67394) (BuildId: 701a4a2915f2955b0f55194896fb996bae90a143)

Address 0x7feea462632b is located in stack of thread T0 at offset 43 in frame
    #0 0x5632c6779dcf in test::StringTest_TestStringView_Test::TestBody() /root/work/xlab/cc/cclab/test/common/string_test.cc:45

  This frame has 2 object(s):
    [32, 43) 'hello' (line 47) <== Memory access at offset 43 overflows this variable
    [64, 80) 'sub' (line 48)
HINT: this may be a false positive if your program uses some custom stack unwind mechanism, swapcontext or vfork
      (longjmp and C++ exceptions *are* supported)
 * 
 */
TEST_F(StringTest, TestStringView) {
    char next[] = {'n','e','x','t'};
    char hello[] = {'H','e','l','l','o', ' ', 'W','o','r','l','d'};
    // std::string_view sub(hello, 5);
    // std::string_view sub(hello);
    // std::cout << sub << "\n";
    // print_me(sub);
}


} // namespace test