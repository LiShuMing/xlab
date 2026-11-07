/**
 * 前缀和 & 差分（OI Wiki 笔记 + 例程）
 *
 * 一句话：前缀和把「区间求和」预处理成 O(1) 查询；差分是它的逆运算，把「区间加」
 * 预处理成 O(1) 修改，改动全部做完后再用前缀和还原。
 *
 * 一维：
 *   S[i] = S[i-1] + a[i]（S[0] = 0），所以 sum(l..r) = S[r] - S[l-1]
 *   D[i] = a[i] - a[i-1]，a 就是 D 的前缀和；对 [l, r] 整体加 v 只动两端：
 *   D[l] += v, D[r+1] -= v
 *
 * 约束：差分套路要求「先全部改完，再查询」；改查交错就要上树状数组/线段树，
 * 但思想同源——都是把区间操作摊到端点上。
 *
 * 二维（容斥）：
 *   S[i][j] = A[i][j] + S[i-1][j] + S[i][j-1] - S[i-1][j-1]
 *   子矩阵 (x1,y1)..(x2,y2)：S[x2][y2] - S[x1-1][y2] - S[x2][y1-1] + S[x1-1][y1-1]
 *   矩形加 v 落在差分矩阵四个角：+v, -v, -v, +v。
 *   高维不要硬写 2^k 项容斥，用逐维前缀/差分，复杂度 O(kN)。
 *
 * 树上（竞赛高频）：
 *   点权路径 (x, y)：S[x] + S[y] - S[lca] - S[fa(lca)]
 *   边权路径：      S[x] + S[y] - 2 * S[lca]（边权挂在子结点上）
 *   点差分路径加 v：D[x] += v, D[y] += v, D[lca] -= v, D[fa(lca)] -= v，
 *                  最后做一次子树和还原
 *   （USACO Max Flow：K 条路径给点加压，求最大压力，就是这套）
 *
 * 子集和 DP（SOS）：g(S) = sum(T ⊆ S) f(T) 就是 n 维、每维只有 {0,1} 的前缀和，
 * 逐维做 O(n * 2^n)。
 *
 * 坑：下标从 1 开始、l-1 别漏；二维四个角符号容易反；树上点差分与边差分公式差
 * 一个 fa(lca) / 2 * S[lca]；改查混用别硬套裸差分。
 *
 * 参考：https://oi-wiki.org/basic/prefix-sum/
 */

#include "../include/fwd.h"

#include <cassert>
#include <random>  // fwd.h 未包含：随机对拍需要 mt19937 / 取模取样

/**
 * LeetCode 1292. Maximum Side Length of a Square with Sum Less than or Equal to Threshold
 * https://leetcode.com/problems/maximum-side-length-of-a-square-with-sum-less-than-or-equal-to-threshold/
 *
 * 题意：n x m 的非负矩阵 mat 和阈值 threshold，求「元素和 <= threshold」的正方形的
 * 最大边长；不存在则返回 0。（注意不是「全 1 最大正方形」，那题没有 threshold。）
 *
 * 思路：二维前缀和 O(1) 求任意子方阵和；边长 len 可行则所有更小边长也可行
 * （元素非负，单调性成立），于是对边长二分。
 *
 * Time:  O(m * n * log(min(m, n)))
 * Space: O(m * n)
 *
 * 旁注：本题还有 O(m * n) 的写法——答案边长每向右下走一格最多 +1，用前缀和逐格
 * 判断「边长 +1 是否仍可行」即可，不需要二分。这里保留二分版，因为它更能体现
 * 「前缀和 + 单调性判定」这个通用套路。
 */
class Solution {
public:
    // 签名由评测机固定，保持 camelCase
    int maxSideLength(std::vector<std::vector<int>>& mat, int threshold) {
        const int rows = static_cast<int>(mat.size());
        const int cols = static_cast<int>(mat[0].size());

        // 前缀和多留一行一列 0，免去 i-1 / j-1 的越界判断；用 long long：本题上限
        // 300*300*1e4 = 9e8 刚好卡在 int 里，元素或维度再大一点就会溢出
        std::vector<std::vector<long long>> prefix(rows + 1, std::vector<long long>(cols + 1, 0));
        for (int i = 1; i <= rows; ++i) {
            for (int j = 1; j <= cols; ++j) {
                prefix[i][j] = mat[i - 1][j - 1] + prefix[i - 1][j] + prefix[i][j - 1] -
                               prefix[i - 1][j - 1];
            }
        }

        // 二分最后一个可行边长；mid 上取整，区间退化到 low == high 时不会死循环
        int low = 0;
        int high = std::min(rows, cols);
        while (low < high) {
            const int mid = low + (high - low + 1) / 2;
            if (Fits(prefix, mid, rows, cols, threshold)) {
                low = mid;
            } else {
                high = mid - 1;
            }
        }
        return low;
    }

private:
    // 是否存在边长 len 的可行子方阵：(i, j) 为右下角，左上角为 (i-len, j-len)
    static bool Fits(const std::vector<std::vector<long long>>& prefix, int len, int rows,
                     int cols, int threshold) {
        for (int i = len; i <= rows; ++i) {
            for (int j = len; j <= cols; ++j) {
                const long long sum = prefix[i][j] - prefix[i - len][j] - prefix[i][j - len] +
                                      prefix[i - len][j - len];
                if (sum <= threshold) return true;
            }
        }
        return false;
    }
};

namespace {

// 独立基线：枚举边长 + 逐格累加，完全不用前缀和，用来证伪上面的二分实现。
// 边长从小到大枚举，最后一次命中的 len 就是最大可行边长。
int BruteForce(const std::vector<std::vector<int>>& mat, int threshold) {
    const int rows = static_cast<int>(mat.size());
    const int cols = static_cast<int>(mat[0].size());
    int best = 0;
    for (int len = 1; len <= std::min(rows, cols); ++len) {
        for (int i = 0; i + len <= rows; ++i) {
            for (int j = 0; j + len <= cols; ++j) {
                long long sum = 0;
                for (int x = i; x < i + len; ++x) {
                    for (int y = j; y < j + len; ++y) sum += mat[x][y];
                }
                if (sum <= threshold) best = len;
            }
        }
    }
    return best;
}

// 期望值一律由基线现场算出，不抄「记忆里的样例答案」
void Check(const std::vector<std::vector<int>>& mat, int threshold) {
    Solution solution;
    std::vector<std::vector<int>> input = mat;  // 主解法不得改写入参
    const int got = solution.maxSideLength(input, threshold);
    const int want = BruteForce(mat, threshold);
    if (got != want) {
        std::cout << "FAIL: threshold=" << threshold << " got=" << got << " want=" << want
                  << std::endl;
    }
    assert(got == want);
    assert(input == mat);  // 入参保持原样
}

}  // namespace

int main() {
    // 1) 固定用例（期望值由基线算出）
    Check({{1, 1, 3, 2, 4, 3, 2}, {1, 1, 3, 2, 4, 3, 2}, {1, 1, 3, 2, 4, 3, 2}}, 4);
    Check({{1, 1, 1, 1}, {1, 0, 0, 0}}, 0);  // 只有单格 0 可行 -> 1
    Check({{2, 2}, {2, 2}}, 1);              // 单格 2 已超阈值 -> 0
    Check({{5}}, 4);                         // 单格超阈值 -> 0
    Check({{5}}, 5);                         // 单格刚好等于阈值 -> 1
    Check(std::vector<std::vector<int>>(2, std::vector<int>(5, 1)), 6);    // 非方阵 -> 2
    Check(std::vector<std::vector<int>>(3, std::vector<int>(3, 9)), 8);    // 全超阈值 -> 0

    // 2) 随机对拍：小规模下基线足够快，覆盖方阵/长条/全 0/threshold 极端值
    std::mt19937 random_engine(20261107);
    constexpr int kRounds = 3000;
    for (int round = 0; round < kRounds; ++round) {
        const int rows = 1 + static_cast<int>(random_engine() % 6);
        const int cols = 1 + static_cast<int>(random_engine() % 6);
        const int max_value = static_cast<int>(random_engine() % 4);  // 元素 0..3
        std::vector<std::vector<int>> mat(rows, std::vector<int>(cols, 0));
        int total = 0;
        for (auto& row : mat) {
            for (int& value : row) {
                value = static_cast<int>(random_engine() % (max_value + 1));
                total += value;
            }
        }
        // threshold 覆盖「全部不可行」(0) 到「全部可行」(total) 以及再大一点
        const int threshold = static_cast<int>(random_engine() % (total + 2));
        Check(mat, threshold);
    }
    std::cout << "[前缀和] " << kRounds << " 轮随机对拍一致" << std::endl;

    // 3) 大规模冒烟：300x300 全 1，阈值 10000 -> 边长 100
    //    （100*100 = 10000 刚好可行，101*101 = 10201 超阈值，可解析验证）
    std::vector<std::vector<int>> ones(300, std::vector<int>(300, 1));
    Solution solution;
    const int side = solution.maxSideLength(ones, 10000);
    std::cout << "[前缀和] 300x300 全 1, threshold=10000 => " << side << std::endl;
    assert(side == 100);

    // 4) 全 0 矩阵 + 阈值 0：整个矩阵都可行，答案取 min(rows, cols)
    std::vector<std::vector<int>> zeros(300, std::vector<int>(300, 0));
    assert(solution.maxSideLength(zeros, 0) == 300);

    std::cout << "oi_prefix_sum: all checks passed" << std::endl;
    return 0;
}
