#include "../include/fwd.h"
#include <random>

/**
nums1 中数字 x 的 下一个更大元素 是指 x 在 nums2 中对应位置 右侧 的 第一个 比 x 大的元素。

给你两个 没有重复元素 的数组 nums1 和 nums2 ，下标从 0 开始计数，其中nums1 是 nums2 的子集。

对于每个 0 <= i < nums1.length ，找出满足 nums1[i] == nums2[j] 的下标 j ，并且在 nums2 确定 nums2[j] 的 下一个更大元素 。如果不存在下一个更大元素，那么本次查询的答案是 -1 。

返回一个长度为 nums1.length 的数组 ans 作为答案，满足 ans[i] 是如上所述的 下一个更大元素 。
 */
class Solution {
public:
    vector<int> nextGreaterElement(vector<int>& nums1, vector<int>& nums2) {
        // 先对 nums2 一次性算出「值 -> 下一个更大元素」的整张表，
        // 再按 nums1 查表。能这样做是因为题目保证元素不重复（值可以当 key）。
        unordered_map<int, int> nextGreater;
        stack<int> candidates;  // 单调栈：栈顶是「最靠左的候选」里最小的那个

        // 从右往左扫：处理 x 时，它右边的元素都已经进过栈了。
        for (int i = static_cast<int>(nums2.size()) - 1; i >= 0; --i) {
            const int x = nums2[i];
            // 比 x 小（或等）的候选永远不会再被用到：x 既比它们靠左、又比它们大，把它们挡住了。
            while (!candidates.empty() && candidates.top() <= x) candidates.pop();
            nextGreater[x] = candidates.empty() ? -1 : candidates.top();
            candidates.push(x);  // 压自己：对更左边的元素而言，x 是一个更新的候选
        }

        vector<int> ans;
        ans.reserve(nums1.size());
        for (int x : nums1) ans.push_back(nextGreater[x]);  // 题目保证 nums1 是 nums2 的子集
        return ans;
    }
};

// 暴力解：只用来对拍。对 nums1 每个 x，先在 nums2 里定位，再向右找第一个更大值。
static vector<int> bruteForce(const vector<int>& nums1, const vector<int>& nums2) {
    vector<int> ans;
    for (int x : nums1) {
        int res = -1;
        bool seen = false;
        for (int y : nums2) {
            if (!seen) {
                if (y == x) seen = true;  // 还没走到 x 的位置，继续往右
                continue;
            }
            if (y > x) {
                res = y;
                break;
            }
        }
        ans.push_back(res);
    }
    return ans;
}

static string toString(const vector<int>& v) {
    string s = "[";
    for (size_t i = 0; i < v.size(); ++i) s += (i ? ", " : "") + to_string(v[i]);
    return s + "]";
}

int main() {
    Solution solution;

    const struct {
        vector<int> nums1;
        vector<int> nums2;
        vector<int> expect;
    } cases[] = {
        {{4, 1, 2}, {1, 3, 4, 2}, {-1, 3, -1}},  // 官方样例：4 和 2 右边都没有更大的
        {{2, 4}, {1, 2, 3, 4}, {3, -1}},         // 2 的下一个更大是 3，4 没有
        {{1}, {1}, {-1}},                        // 只有一个元素
        {{3, 2}, {3, 2, 1}, {-1, -1}},           // 全程递减：一个都找不到
        {{1, 2, 3}, {1, 2, 3}, {2, 3, -1}},      // 全程递增：只有最右边没答案
    };

    int failed = 0;
    for (const auto& c : cases) {
        auto nums1 = c.nums1;  // 形参是 vector<int>&（力扣签名），传拷贝才能接 const 用例
        auto nums2 = c.nums2;
        const vector<int> got = solution.nextGreaterElement(nums1, nums2);
        cout << "nextGreaterElement(" << toString(nums1) << ", " << toString(nums2)
             << ") = " << toString(got) << "  expect " << toString(c.expect)
             << (got == c.expect ? "  OK" : "  FAIL") << endl;
        if (got != c.expect) ++failed;
    }

    // 与暴力解随机对拍：nums2 取 0..k-1 的排列（保证不重复），nums1 取它的随机非空子集
    mt19937 rng(496);
    int tested = 0;
    for (int round = 0; round < 2000; ++round) {
        const int k = static_cast<int>(rng() % 8) + 1;
        vector<int> nums2(k);
        iota(nums2.begin(), nums2.end(), 0);
        shuffle(nums2.begin(), nums2.end(), rng);

        vector<int> nums1;
        for (int v : nums2) {
            if (rng() % 2) nums1.push_back(v);
        }
        if (nums1.empty()) nums1.push_back(nums2[0]);

        const vector<int> got = solution.nextGreaterElement(nums1, nums2);
        const vector<int> want = bruteForce(nums1, nums2);
        ++tested;
        if (got != want) {
            ++failed;
            if (failed <= 5) {
                cout << "MISMATCH nums1=" << toString(nums1) << " nums2=" << toString(nums2)
                     << " got=" << toString(got) << " want=" << toString(want) << endl;
            }
        }
    }
    cout << "random cases tested = " << tested << endl;

    cout << (failed == 0 ? "leetcode_496: all checks passed" : "leetcode_496: FAILED") << endl;
    return failed == 0 ? 0 : 1;
}
