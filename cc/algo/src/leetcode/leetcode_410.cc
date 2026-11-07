#include "../include/fwd.h"

#include <random>

/**
 * LeetCode 410. Split Array Largest Sum
 *
 * 非负数组切成 k 段非空连续子数组，最小化最大段和。
 * “至多 k 段”与“恰好 k 段”答案相同：非负前提下补切只会增加段数、不增大最大值。
 *
 * 二分的三个易错点：下界必须取 max(nums)、中点要防溢出、hi 与累加要用 long long。
 */
class Solution {
public:
    // 二分答案 + 贪心判定，O(N log S)，S 为总和
    int splitArray(vector<int>& nums, int k) {
        long long lo = 0, hi = 0;
        for (int x : nums) {
            lo = max(lo, static_cast<long long>(x));
            hi += x;
        }
        while (lo < hi) {
            long long mid = lo + (hi - lo) / 2;  // 不用 (lo + hi) / 2，避免先溢出
            if (feasible(nums, mid, k)) {
                hi = mid;
            } else {
                lo = mid + 1;
            }
        }
        return static_cast<int>(lo);
    }

    // DP 参考解：O(k N^2)，思路与二分完全不同，只用来对拍
    long long splitArrayDp(const vector<int>& nums, int k) {
        int n = nums.size();
        if (k > n) return -1;  // 题目保证不会出现
        const long long kInf = numeric_limits<long long>::max() / 4;
        vector<long long> prefix(n + 1, 0);
        for (int i = 0; i < n; ++i) prefix[i + 1] = prefix[i] + nums[i];
        // dp[j][i]：前 i 个元素切成 j 段时的最小最大段和
        vector<vector<long long>> dp(k + 1, vector<long long>(n + 1, kInf));
        dp[0][0] = 0;
        for (int j = 1; j <= k; ++j) {
            for (int i = j; i <= n; ++i) {
                for (int p = j - 1; p < i; ++p) {
                    long long cand = max(dp[j - 1][p], prefix[i] - prefix[p]);
                    dp[j][i] = min(dp[j][i], cand);
                }
            }
        }
        return dp[k][n];
    }

    // 反面教材：下界写成 0。元素比 mid 大时贪心只会多切一刀，不会报告“装不下”，
    // 于是判定谎报可行，二分收敛到比最大元素还小的值。
    int buggyNoLowerBound(const vector<int>& nums, int k) {
        long long lo = 0, hi = 0;
        for (int x : nums) hi += x;
        while (lo < hi) {
            long long mid = lo + (hi - lo) / 2;
            if (feasible(nums, mid, k)) {
                hi = mid;
            } else {
                lo = mid + 1;
            }
        }
        return static_cast<int>(lo);
    }

private:
    // 给定容量，贪心装满即换段，判断能否用不超过 k 段装完
    bool feasible(const vector<int>& nums, long long cap, int k) {
        int need = 1;
        long long cur = 0;
        for (int x : nums) {
            if (cur + x > cap) {
                ++need;
                cur = x;
            } else {
                cur += x;
            }
        }
        return need <= k;
    }
};

static string joinNums(const vector<int>& nums) {
    string s;
    for (size_t i = 0; i < nums.size(); ++i) {
        s += (i ? ", " : "") + to_string(nums[i]);
    }
    return "[" + s + "]";
}

int main() {
    Solution sol;

    struct Case {
        vector<int> nums;
        int k;
        int expect;
    };
    vector<Case> cases = {
        {{7, 2, 5, 10, 8}, 2, 18},          // 标准样例
        {{1, 2, 3, 4, 5}, 2, 9},            // 切在 4 与 5 之间
        {{1, 4, 4}, 3, 4},                  // k == n，答案就是最大元素
        {{0, 0, 0}, 2, 0},                  // 全零：下界同样为 0
        {{2147483647, 2147483647}, 2, 2147483647},  // hi = 2 * INT_MAX，用 int 会溢出
        {{2147483647, 0}, 1, 2147483647},   // k == 1，答案是总和
        {{1, 1, 10}, 3, 10}                 // 大元素迫使它独占一段
    };
    for (const auto& c : cases) {
        auto nums = c.nums;
        int bs = sol.splitArray(nums, c.k);
        long long dp = sol.splitArrayDp(c.nums, c.k);
        cout << "nums = " << joinNums(c.nums) << ", k = " << c.k << " -> 二分 = " << bs
             << ", DP = " << dp << endl;
        assert(bs == c.expect);
        assert(dp == c.expect);
    }

    // 把“下界不能写成 0”做成可执行的证据
    vector<int> trap = {1, 1, 10};
    int wrong = sol.buggyNoLowerBound(trap, 3);
    cout << "下界写 0 时 nums = " << joinNums(trap) << ", k = 3 -> " << wrong
         << "（正确值 " << sol.splitArrayDp(trap, 3) << "）" << endl;
    assert(wrong == 1);

    mt19937 rng(20261102);

    // 常规对拍：含 0，n ≤ 10
    for (int round = 0; round < 2000; ++round) {
        int n = 1 + rng() % 10;
        vector<int> nums(n);
        for (int& x : nums) x = rng() % 21;
        int k = 1 + rng() % n;
        auto copy = nums;
        int bs = sol.splitArray(copy, k);
        long long dp = sol.splitArrayDp(nums, k);
        if (bs != dp) {
            cout << "MISMATCH round=" << round << " nums = " << joinNums(nums) << ", k = " << k
                 << " 二分=" << bs << " DP=" << dp << endl;
            return 1;
        }
    }

    // 大值对拍：专门压 hi 与累加的溢出
    for (int round = 0; round < 200; ++round) {
        int n = 2 + rng() % 4;
        vector<int> nums(n);
        for (int& x : nums) x = INT_MAX - static_cast<int>(rng() % 5);
        int k = 1 + rng() % n;
        long long dp = sol.splitArrayDp(nums, k);
        if (dp > INT_MAX) continue;  // 题目保证结果能放进 int，越界的输入不参与比较
        auto copy = nums;
        int bs = sol.splitArray(copy, k);
        if (bs != dp) {
            cout << "MISMATCH(大值) round=" << round << " nums = " << joinNums(nums)
                 << ", k = " << k << " 二分=" << bs << " DP=" << dp << endl;
            return 1;
        }
    }

    cout << "随机对拍通过：二分 2200 轮 vs DP 全部一致" << endl;
    return 0;
}
