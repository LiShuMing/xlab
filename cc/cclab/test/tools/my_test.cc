#include <gtest/gtest.h>

#include <atomic>
#include <cstring>
#include <functional>
#include <iostream>
#include <list>
#include <map>
#include <queue>
#include <shared_mutex>
#include <stack>
#include <string>
#include <vector>

#include "utils/defer.h"
#include <iostream>
#include <string>
#include <vector>
#include <unordered_map>

template <typename TSubclass>
class TestRegistrar {
public:
    using subclass_t = TSubclass;

    void registerTest(const char* name, bool (subclass_t::* method)()) {
        testVec.push_back(std::make_pair(std::string(name), method));
        testMap[std::string(name)] = method;
    }

    // 调用测试方法
    bool runTest(const char* name, subclass_t& instance) {
        auto it = testMap.find(std::string(name));
        if (it != testMap.end()) {
            bool (subclass_t::* method)() = it->second;
            return (instance.*method)(); // 调用方法
        }
        std::cerr << "Test not found: " << name << std::endl;
        return false;
    }

private:
    std::vector<std::pair<std::string, bool (subclass_t::*)()>> testVec;
    std::unordered_map<std::string, bool (subclass_t::*)()> testMap;
};

// 示例类
class MyTests {
public:
    bool test1() {
        std::cout << "Running test1..." << std::endl;
        return true;
    }
    bool test2() {
        std::cout << "Running test2..." << std::endl;
        return false;
    }
};

int main() {
    TestRegistrar<MyTests> registrar;

    MyTests tests;

    // 注册测试
    registrar.registerTest("Test1", &MyTests::test1);
    registrar.registerTest("Test2", &MyTests::test2);

    // 运行测试
    registrar.runTest("Test1", tests);
    registrar.runTest("Test2", tests);
    registrar.runTest("Test3", tests); // 测试不存在的情况

    return 0;
}