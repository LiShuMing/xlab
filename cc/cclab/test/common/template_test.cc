#include <gtest/gtest.h>

#include <algorithm> // new fold_left, ends_with
#include <atomic>
#include <cctype>
#include <cstring>
#include <functional>
#include <iostream>
#include <list>
#include <map>
#include <memory>
#include <numeric>
#include <queue>
#include <ranges>
#include <shared_mutex>
#include <string>
#include <vector>

#include "common/cow.h"

using namespace std;

namespace test {

// Basic Test
class TemplateTest : public testing::Test {};

using namespace std;

template <typename Derived>
class Base {
public:
    void interface() {
        static_cast<Derived*>(this)->implementation();
    }
};

template <typename Derived>
class Intermediate : public Base<Derived> {
public:
    void implementation() {
        std::cout << "Intermediate implementation" << std::endl;
    }
};

class Derived : public Intermediate<Derived> {
public:
    void implementation() {
        std::cout << "Derived implementation" << std::endl;
    }
};

TEST_F(TemplateTest, TestBasic) {
    Derived obj;
    obj.interface(); // expect: Derived implementation
}

} // namespace test
