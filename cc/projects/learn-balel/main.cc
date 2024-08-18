// main.cc
#include <iostream>
#include "math_util.h"
#include "fmt/core.h"

int main() {
    int a = 10;
    int b = 20;
    int result = add(a, b);

    fmt::print("计算结果: {} + {} = {}\n", a, b, result);

    return 0;
}
