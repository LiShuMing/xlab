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

#include "utils/task_thread.h"

using namespace std;

namespace test {

// Basic Test
class TaskThreadTest : public testing::Test {};

void func1() { cout << "func1" << endl; }

void func2(int a) { cout << "func2: " << a << endl; }

class Foo {
  public:
    void func3(int b) { cout << "func3: " << b << endl; }
};

TEST_F(TaskThreadTest, Test1) {
    xlab::TaskThread tt("test", xlab::TaskThread::ReleaseMode::RELEASE_MODE_DO_ALL_DONE);
    tt.start();
    tt.add(std::bind(&func1));
    tt.add(std::bind(&func2, 10));
    Foo foo;
    tt.add(std::bind(&Foo::func3, &foo, 20));
    tt.stop_and_join();
}

} // namespace test

int main(int argc, char **argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
