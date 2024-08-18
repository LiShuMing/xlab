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

#include "utils/os_exec_op.h"

using namespace std;

namespace test {

// Basic Test
class OpExecOpTest : public testing::Test {};

TEST_F(OpExecOpTest, Test1) {
    bool succ;
    int exit_status;
    std::string filename = std::string("/tmp/os_op_test_") + std::to_string(std::time(0));

    // test >> file
    std::string cmd_touch = std::string("echo \"hello\nworld\" >> ") + filename;
    std::vector<std::string> output_touch;
    succ = xlab::OsExecOp::run_command(cmd_touch, &output_touch, &exit_status);
    GTEST_ASSERT_TRUE(succ && output_touch.empty() && exit_status == 0);

    // test cat file
    std::string cmd_cat = "cat " + filename;
    std::vector<std::string> output_cat;
    succ = xlab::OsExecOp::run_command(cmd_cat, &output_cat, &exit_status);
    GTEST_ASSERT_TRUE(succ && output_cat.size() == 2 && output_cat[0] == "hello" &&
                      output_cat[1] == "world" && exit_status == 0);

    // test rm file
    std::string cmd_rm = "rm " + filename;
    std::vector<std::string> output_rm;
    succ = xlab::OsExecOp::run_command(cmd_rm, &output_rm, &exit_status);
    GTEST_ASSERT_TRUE(succ && output_rm.empty() && exit_status == 0);

    // test bad command
    std::string cmd_not_exist = std::string("/tmp/cmd_not_exist_") + std::to_string(std::time(0));
    std::vector<std::string> output_cmd_not_exist;
    succ = xlab::OsExecOp::run_command(cmd_not_exist, &output_cmd_not_exist, &exit_status);
    GTEST_ASSERT_TRUE(succ && output_cmd_not_exist.empty() && exit_status != 0);

    std::string cmd_rm_not_exist =
            std::string("rm /tmp/file_not_exist_") + std::to_string(std::time(0));
    std::vector<std::string> output_cmd_rm_not_exist;
    succ = xlab::OsExecOp::run_command(cmd_rm_not_exist, &output_cmd_rm_not_exist, &exit_status);
    assert(succ && output_cmd_not_exist.empty() && exit_status != 0);
}

} // namespace test