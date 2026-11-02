#include "../include/fwd.h"
#include <random>

// LeetCode 76. 最小覆盖子串
// 题意：在 s 中找最短的连续子串，使其包含 t 的全部字符（同一字符按重复次数计）。
//
// 面试版滑窗模板，三块结构：
//   1) 统计需求：need[c] = 还需要几个 c，required = 有多少种字符需要
//   2) 右扩：win[c] 记录窗口内计数，某种字符“恰好凑齐”时 formed++
//   3) 左缩：formed == required 说明窗口可行，先记答案再吐出一个左字符
// 进窗与出窗是两个完全对称的判断，只需记住 ++win[c] == need[c] 与 win[d]-- == need[d]。
//
// 为什么不用“一个数组存正负三态”：那种写法省一个数组，却让同一个变量同时表达
// "需求"和"窗口余量"，手写时非常容易把判断条件写反。两个数组语义单一，更不容易错。
//
// 复杂度：时间 O(|s| + |t|)，空间 O(1)（256 个计数桶）。
class Solution {
public:
    string minWindow(const string& s, const string& t) {
        if (t.empty() || t.size() > s.size()) return "";

        int need[256] = {0};
        int required = 0;
        for (char c : t) {
            if (need[static_cast<unsigned char>(c)]++ == 0) ++required;
        }

        int win[256] = {0};
        int formed = 0;  // 已经凑齐配额的字符种类数
        int bestLen = INT_MAX, bestStart = 0, l = 0;
        const int n = static_cast<int>(s.size());

        for (int r = 0; r < n; ++r) {
            const unsigned char c = static_cast<unsigned char>(s[r]);
            if (need[c] > 0 && ++win[c] == need[c]) ++formed;  // 刚好凑齐

            while (formed == required) {  // 窗口已覆盖 t：先结算，再试着左缩
                if (r - l + 1 < bestLen) {
                    bestLen = r - l + 1;
                    bestStart = l;
                }
                const unsigned char d = static_cast<unsigned char>(s[l++]);
                if (need[d] > 0 && win[d]-- == need[d]) --formed;  // 不再凑齐
            }
        }
        return bestLen == INT_MAX ? "" : s.substr(bestStart, bestLen);
    }
};

namespace {

// 暴力对照：按起点、终点升序枚举所有子串。起点固定时第一个可行子串就是该起点的
// 最短窗口；跨起点只在严格更短时覆盖，因此结果天然是"最左的最短窗口"。
string bruteMinWindow(const string& s, const string& t) {
    if (t.empty() || t.size() > s.size()) return "";
    const size_t n = s.size();
    string best;
    for (size_t i = 0; i < n; ++i) {
        for (size_t j = i + t.size() - 1; j < n; ++j) {
            int need[256] = {0};
            for (char c : t) ++need[static_cast<unsigned char>(c)];
            for (size_t k = i; k <= j; ++k) --need[static_cast<unsigned char>(s[k])];
            bool covered = true;
            for (int v : need) {
                if (v > 0) {
                    covered = false;
                    break;
                }
            }
            if (!covered) continue;
            if (best.empty() || j - i + 1 < best.size()) best = s.substr(i, j - i + 1);
            break;
        }
    }
    return best;
}

}  // namespace

int main() {
    Solution sol;

    struct Case {
        string s;
        string t;
        string expect;
    };
    const vector<Case> cases = {
        {"ADOBECODEBANC", "ABC", "BANC"},          // 题面样例
        {"a", "a", "a"},                           // 单字符命中
        {"a", "aa", ""},                           // t 字符数超出 s
        {"aa", "aa", "aa"},                        // 必须按重复次数覆盖
        {"cabwefgewcwaefgcf", "cae", "cwae"},      // 窗口内字符乱序
        {"abc", "cba", "abc"},                     // t 本身是 s 的排列
        {"ab", "b", "b"},                          // 单字符覆盖
        {"aaaaaaaaaaaabbbbbcdd", "abcdd", "abbbbbcdd"},  // 重复字符凑配额
        {"abc", "", ""},                           // t 为空的守卫
    };

    int failed = 0;
    for (const auto& c : cases) {
        const string got = sol.minWindow(c.s, c.t);
        const bool ok = (got == c.expect);
        if (!ok) ++failed;
        cout << (ok ? "PASS" : "FAIL") << "  s=\"" << c.s << "\"  t=\"" << c.t
             << "\"  got=\"" << got << "\"  expect=\"" << c.expect << "\"" << endl;
    }

    // 随机对拍：小字符集 + 短串，覆盖大量"窗口边界刚好卡住"的情形
    mt19937 rng(76);
    const string alphabet = "abc";
    int rounds = 0;
    for (int iter = 0; iter < 5000 && failed == 0; ++iter) {
        const int n = 1 + static_cast<int>(rng() % 12);
        string s;
        for (int i = 0; i < n; ++i) s.push_back(alphabet[rng() % alphabet.size()]);

        const int m = 1 + static_cast<int>(rng() % 5);
        string t;
        for (int i = 0; i < m; ++i) t.push_back(alphabet[rng() % alphabet.size()]);

        const string got = sol.minWindow(s, t);
        const string expect = bruteMinWindow(s, t);
        if (got != expect) {
            cout << "FAIL  random  s=\"" << s << "\"  t=\"" << t << "\"  got=\"" << got
                 << "\"  expect=\"" << expect << "\"" << endl;
            ++failed;
            break;
        }
        ++rounds;
    }
    cout << "random cross-check: " << rounds << " rounds" << endl;

    cout << (failed == 0 ? "leetcode_76: all checks passed" : "leetcode_76: FAILED") << endl;
    return failed == 0 ? 0 : 1;
}
