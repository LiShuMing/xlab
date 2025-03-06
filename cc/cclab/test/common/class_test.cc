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

using namespace std;

namespace test {

// Basic Test
class ClassTest : public testing::Test {};

class TestClass1 {
  public:
    TestClass1(std::shared_ptr<int> data, std::vector<string> names) : _data(data), _names(names) {}

    std::shared_ptr<int> get_data() const { return _data; }
    std::vector<string> get_names() const { return _names; }

  private:
    std::shared_ptr<int> _data;
    std::vector<string> _names;
};
class TestClass2 {
  public:
    TestClass2(std::shared_ptr<int> data, std::vector<string> names)
        : _data(std::move(data)), _names(std::move(names)) {}

    std::shared_ptr<int> get_data() const { return _data; }
    std::vector<string> get_names() const { return _names; }

  private:
    std::shared_ptr<int> _data;
    std::vector<string> _names;
};

class TestClass3 {
  public:
    TestClass3(std::shared_ptr<int> &&data, std::vector<string> &&names)
        : _data(std::move(data)), _names(std::move(names)) {}

    std::shared_ptr<int> get_data() const { return _data; }
    std::vector<string> get_names() const { return _names; }

  private:
    std::shared_ptr<int> _data;
    std::vector<string> _names;
};

class TestClass4 {
  public:
    // why const std::vector<string> &names can compile ok even by using std::move(names)
    // const std::vector<string> &names is a const reference, so it cannot be moved, original names
    // is still valid
    TestClass4(std::shared_ptr<int> &data, std::vector<string> &names)
        : _data(std::move(data)), _names(std::move(names)) {}

    std::shared_ptr<int> get_data() const { return _data; }
    std::vector<string> get_names() const { return _names; }

  private:
    std::shared_ptr<int> _data;
    std::vector<string> _names;
};
void print_data_names(const std::shared_ptr<int> &data, const std::vector<string> &names) {
    std::cout << "START" << std::endl;
    if (data) {
        std::cout << "data:" << *data;
    } else {
        std::cout << "data: nullptr";
    }
    for (const auto &name : names) {
        std::cout << ", name:" << name;
    }
    std::cout << std::endl << std::endl;
}

TestClass2 create_test_class2() {
    std::shared_ptr<int> data = std::make_shared<int>(1);
    std::vector<string> names = {"a", "b", "c"};
    return TestClass2(std::move(data), std::move(names));
}

TestClass3 create_test_class3() {
    std::shared_ptr<int> data = std::make_shared<int>(1);
    std::vector<string> names = {"a", "b", "c"};
    return TestClass3(std::move(data), std::move(names));
}
TestClass4 create_test_class4() {
    std::shared_ptr<int> data = std::make_shared<int>(1);
    std::vector<string> names = {"a", "b", "c"};
    // : cannot bind non-const lvalue reference of type ‘std::shared_ptr<int>&’ to an rvalue of type ‘std::remove_reference<std::shared_ptr<int>&>::type’ {aka ‘std::shared_ptr<int>’}
    // return TestClass4(std::move(data), std::move(names));
    return TestClass4(data, names);
}

TEST_F(ClassTest, TestClass2) {
    {
        TestClass2 test1 = create_test_class2();
        print_data_names(test1.get_data(), test1.get_names());
    }
    {
        TestClass3 test1 = create_test_class3();
        print_data_names(test1.get_data(), test1.get_names());
    }
    {
        TestClass4 test1 = create_test_class4();
        print_data_names(test1.get_data(), test1.get_names());
    }
}
TEST_F(ClassTest, TestClass1) {
    {
        // test TestClass1
        std::shared_ptr<int> data = std::make_shared<int>(1);
        std::vector<string> names = {"a", "b", "c"};
        print_data_names(data, names);
        TestClass1 test1(data, names);

        print_data_names(test1.get_data(), test1.get_names());
        print_data_names(data, names);
    }

    {
        // test TestClass2
        std::shared_ptr<int> data = std::make_shared<int>(1);
        std::vector<string> names = {"a", "b", "c"};
        print_data_names(data, names);
        TestClass2 test1(data, names);

        print_data_names(test1.get_data(), test1.get_names());
        print_data_names(data, names);
    }

    {
        // test TestClass3
        std::shared_ptr<int> data = std::make_shared<int>(1);
        std::vector<string> names = {"a", "b", "c"};
        print_data_names(data, names);

        // this will fail in compile
        // TestClass3 test1(data, names);
        TestClass3 test1(std::move(data), std::move(names));

        print_data_names(test1.get_data(), test1.get_names());
        print_data_names(data, names);
    }
    {
        // test TestClass4
        std::shared_ptr<int> data = std::make_shared<int>(1);
        std::vector<string> names = {"a", "b", "c"};
        print_data_names(data, names);
        TestClass4 test1(data, names);
        print_data_names(test1.get_data(), test1.get_names());
        print_data_names(data, names);
    }
}

class Base {
    public:
        Base() { std::cout << "Base constructor" << std::endl; }
        virtual ~Base() { std::cout << "Base destructor" << std::endl; }
        void print() { std::cout << "Base print" << std::endl; }
};
class Derived : public Base {
    public:
        Derived() { std::cout << "Derived constructor" << std::endl; }
        ~Derived() { std::cout << "Derived destructor" << std::endl; }
};

// cannot use &, but can use
// using Callback = std::function<void(std::shared_ptr<Base>&)>;
using Callback = std::function<void(std::shared_ptr<Base>)>;

class A {
    public:
        A() : _b(std::make_shared<Base>()), _d(std::make_shared<Derived>()) {}
        void for_each_subcolumn(Callback callback) {
            callback(_b);
            callback(_d);
        }
    
    private:
        std::shared_ptr<Base> _b;
        std::shared_ptr<Derived> _d;

};
TEST_F(ClassTest, TestBaseDerived) {
    auto a = std::make_shared<A>();
    a->for_each_subcolumn([](std::shared_ptr<Base> b) {
        b->print();
    });
}

} // namespace test