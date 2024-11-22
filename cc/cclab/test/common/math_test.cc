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
#include <cmath>
#include <iomanip>

#include "utils/foo.h"

using namespace std;

namespace test {

// Basic Test
class MathTest : public testing::Test {};

static const double MAX_EXP_PARAMETER = std::log(std::numeric_limits<double>::max());

bool is_invalid(double value) { return std::isnan(value) || value > MAX_EXP_PARAMETER; }

TEST_F(MathTest, TestExp) {
    //double x = 6.94034278716657;
    // double x = 7.94034278716656984;
    cout << std::setprecision(15);

    double x = -((8.35959286 * 0.396549106 + 6.25989025 * 0.077361308 ) +(-10.73960516));
    cout << "MAX_EXP_PARAMETER = " << MAX_EXP_PARAMETER << endl;
    if (is_invalid(x)) {
        cout << "exp(" << x << ") is invalid" << endl;
    } else {
        cout << "exp(" << x << ") is valid" << endl;
    }
    double y = exp(x);
    cout << "exp(" << x << ") = " << y << endl;
}

} // namespace test

int main(int argc, char** argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
