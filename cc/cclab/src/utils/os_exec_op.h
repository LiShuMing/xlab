
#pragma once
#include <stdio.h>
#include <string.h>

/**
 * Exec shell command and get result in blocking mode
 */

#include <string>
#include <vector>

namespace xlab {

class OsExecOp {
  public:
    /**
     * Open child process to execute shell command and wait for result in blocking mode
     * @return true if command executed successfully, false otherwise
     */
    static bool run_command(const std::string &cmd, std::vector<std::string> *output_lines,
                            int *exit_status);

  private:
    OsExecOp();
    OsExecOp(const OsExecOp &);
    OsExecOp &operator=(const OsExecOp &);

}; // class OsExecOp

} // namespace xlab

namespace xlab {

inline bool OsExecOp::run_command(const std::string &cmd, std::vector<std::string> *output_lines,
                                  int *exit_status) {
    FILE *fp = popen(cmd.c_str(), "r");
    if (!fp) {
        return false;
    }

    static const int MAX_LEN = 16384;
    char line[MAX_LEN] = {0};
    for (; fgets(line, MAX_LEN, fp);) {
        size_t rend = strlen(line) - 1;
        if (line[rend] == '\n') {
            line[rend] = '\0';
        }

        if (output_lines) {
            output_lines->push_back(line);
        }
    }
    int es = pclose(fp);
    if (es == -1) {
        return false;
    }

    if (exit_status) {
        *exit_status = es;
    }

    return true;
}

} // namespace xlab