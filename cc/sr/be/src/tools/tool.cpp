
#include <gflags/gflags.h>

#include <fstream>
#include <iostream>
#include <set>
#include <string>

int main(int argc, char** argv) {
    gflags::SetUsageMessage("");
    google::ParseCommandLineFlags(&argc, &argv, true);
    std::cout << "tool" << std::endl;
    return 0;
}