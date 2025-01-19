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
#include <iomanip>


#include "common/cow.h"

using namespace std;

namespace test {

// Basic Test
class DoubleTest : public testing::Test {};

using namespace std;

TEST_F(DoubleTest, TestWithStringInput) {
    std::cout << std::fixed << std::showpoint;
    std::cout << std::setprecision(20);

    std::vector<string> a1{"1.1234568", "0.1", "2.9876542", "0.2"};
    {
        double sum = 0.0;
        for (auto &a : a1) {
            float f = std::strtof(a.c_str(), nullptr);
            sum += f;
        }
        std::cout << "sum:" << sum << std::endl;
        std::cout << "sum:" << (double)sum << std::endl;
    }
    {
        double sum = 0.0;
        for (auto &a : a1) {
            std::istringstream iss(a);
            float f;
            iss >> f;
            if (iss.fail()) {
                std::cerr << "error: " << a << std::endl;
            } else {
                sum += f;
            }
        }
        std::cout << "sum:" << sum << std::endl;
        std::cout << "sum:" << (double)sum << std::endl;
    }
}

TEST_F(DoubleTest, TestBasic) {

    std::vector<float> a1{1.1234568, 0.1, 2.9876542, 0.2};
    {
        float sum = std::accumulate(a1.begin(), a1.end(), 0.0);
        std::cout << "sum:" << sum << std::endl;
    }
    {
        double sum = std::accumulate(a1.begin(), a1.end(), 0.0);
        std::cout << "sum:" << sum << std::endl;
        std::cout << "sum:" << (double)sum << std::endl;
    }
    {
        double sum = 0.0;
        for (auto &a : a1) {
            sum += (double)a;
        }
        std::cout << "sum:" << sum << std::endl;
        std::cout << "sum:" << (double)sum << std::endl;
    }
    {
        double sum{};
        for (auto &a : a1) {
            sum += (double)a;
        }
        std::cout << "sum:" << sum << std::endl;
        std::cout << "sum:" << (double)sum << std::endl;
        std::cout << "sum:" << (float)sum << std::endl;

    }
}

} // namespace test
