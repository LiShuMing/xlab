#include "../include/fwd.h"

/**
* 假设你正在爬楼梯。需要 n 阶你才能到达楼顶。
* 每次你可以爬 1 或 2 个台阶。你有多少种不同的方法可以爬到楼顶呢？
*/
//
// 一维写法（原版，保留作对拍参照）：只记「到达第 i 级的总方案数」
//   dp[i] = dp[i-1] + dp[i-2]
// 它成立的隐含前提：最后一步跨 1 级 / 跨 2 级这两种来源互不重叠，所以直接相加。
//
// 二维写法（本文件主答案）：把「最后一步跨了几级」提升成一个维度
//   dp[i][j] = 走到第 i 级、且最后一步跨了 j 级的方案数（j = 0 表示跨 1 级，j = 1 表示跨 2 级）
//   转移：dp[i][j] = dp[i - 步长][0] + dp[i - 步长][1]
//         ——最后一步跨多大已经定死，前驱必然停在 i - 步长；而前驱那一步跨多大都行，所以两列都要加。
//   答案：dp[n][0] + dp[n][1]（末步跨 1 级或 2 级都是合法的到达方式）
//
// 多开一维到底换来了什么：
//   本题没约束，二维版只是把一维信息显式化，多花 O(n) 空间什么也没换到；
//   但只要题目对「相邻两步」动手，一维就写不出来了。例如「不能连续两次跨 2 级」：
//       dp[i][1] = dp[i - 2][0]      // 末步跨 2 级 ⇒ 前驱的末步必须是跨 1 级
//   二维版只改这一行右边，一维版无从下手——这才是二维状态的价值。
//
// 复杂度：O(n) 时间，O(n) 空间（dp 只依赖前两行，可压成 O(1)，见文件末尾注释）。
// 溢出：n ≤ 45 时答案 1836311903 仍装得下 int，n = 46 起就超了，更大的 n 要换 long long。
int climbStairs1d(int n) {
    if (n == 1) return 1;
    if (n == 2) return 2;
    vector<int> dp(n + 1, 0);
    dp[1] = 1;
    dp[2] = 2;
    for (int i = 3; i <= n; i++) {
        dp[i] = dp[i - 1] + dp[i - 2];
    }
    return dp[n];
}

class Solution {
public:
    int climbStairs(int n) {
        // dp[i][0]：末步跨 1 级；dp[i][1]：末步跨 2 级
        vector<vector<int>> dp(n + 1, vector<int>(2, 0));

        for (int i = 1; i <= n; ++i) {
            for (int step = 1; step <= 2; ++step) {
                const int from = i - step;  // 这一步之前站在哪一级
                if (from == 0) {
                    // 直接从地面跨上来：这是唯一的源头，记 1 种。
                    dp[i][step - 1] = 1;
                } else if (from > 0) {
                    // 前驱停在 from 级，它末步跨几级都行 —— 两列都要累加。
                    dp[i][step - 1] = dp[from][0] + dp[from][1];
                }
                // from < 0 时这一列非法（台阶不够迈），保持 0。
            }
        }
        return dp[n][0] + dp[n][1];
    }
};

int main() {
    Solution solution;

    // 手算可核对的小值：1,2,3,4,5 级分别是 1,2,3,5,8
    const struct {
        int n;
        int expect;
    } cases[] = {
        {1, 1}, {2, 2}, {3, 3}, {4, 5}, {5, 8},
        // LC 70 的上限 n = 45，结果是 fib(46) = 1836311903，刚好还在 int 范围内（n = 46 就溢出了）。
        {45, 1836311903},
    };

    int failed = 0;
    for (const auto& c : cases) {
        const int got = solution.climbStairs(c.n);
        cout << "climbStairs(" << c.n << ") = " << got << "  expect " << c.expect
             << (got == c.expect ? "  OK" : "  FAIL") << endl;
        if (got != c.expect) ++failed;
    }

    // 与一维递推全量对拍：n = 1..45 每一个都必须一致。
    for (int n = 1; n <= 45; ++n) {
        const int two = solution.climbStairs(n);
        const int one = climbStairs1d(n);
        if (two != one) {
            cout << "MISMATCH n=" << n << " 2d=" << two << " 1d=" << one << endl;
            ++failed;
        }
    }

    cout << (failed == 0 ? "leetcode_70: all checks passed" : "leetcode_70: FAILED") << endl;
    return failed == 0 ? 0 : 1;
}

// 空间压缩：dp[i] 只依赖 dp[i-1] 与 dp[i-2]，所以那张二维表可以只留两行滚动；
// 继续压下去就退化成 1D 版的 prev / cur 两个变量——这正是「二维版没换来新信息」的具体表现。
