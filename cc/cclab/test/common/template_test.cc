#include <gtest/gtest.h>

#include <concepts>
#include <cstddef>
#include <functional>
#include <iostream>
#include <type_traits>

#include "common/cow.h"

namespace test {

class TemplateTest : public testing::Test {

};
// Basic Test

template <typename Derived> class Base {
  public:
    void interface() { static_cast<Derived *>(this)->implementation(); }
};

template <typename Derived> class Intermediate : public Base<Derived> {
  public:
    void implementation() { std::cout << "Intermediate implementation" << std::endl; }
};

class Derived : public Intermediate<Derived> {
  public:
    void implementation() { std::cout << "Derived implementation" << std::endl; }
};

TEST_F(TemplateTest, TestBasic) {
    Derived obj;
    obj.interface(); // expect: Derived implementation
}


} // namespace test
