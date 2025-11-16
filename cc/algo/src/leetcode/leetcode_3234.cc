#include "../include/fwd.h"

class Solution {
public:
    int numberOfSubstrings(string s) {
        int n = s.size();
        vector<int> prev(n + 1, 0);
        prev[0] = -1;
        for (int i = 0; i < n; i++) {
            if (i == 0 || (i > 0 && s[i - 1] == '0')) {
                prev[i + 1] = i;
            } else {
                prev[i + 1] = prev[i];
            }
        }
        int ans = 0;
        for (int i = 1; i <= n; i++) {
            int cnt0 = s[i - 1] == '0';
            int j = i;
            while (j > 0 && cnt0 * cnt0 <= n) {
                int cnt1 = i - prev[j] - cnt0;
                if (cnt0 * cnt0 <= cnt1) {
                    ans += min(j - prev[j], cnt1 - cnt0 * cnt0 + 1);
                }
                j = prev[j];
                cnt0++;
            }
        }
        return ans;
    }
};

// LeetCode 3234: Count the Number of Substrings With Dominant Ones
// Time: O(n * sqrt(n)), Space: O(1)
class Solution2 {
    public:
        int numberOfSubstrings(string s) {
            int n = s.size();
            long long ans = 0;
    
            // 枚举合法子串中 0 的数量 zero
            // 只要 zero^2 + zero <= n 就有可能出现
            for (int zero = 0; zero + zero * zero <= n; ++zero) {
                int lastInvalidPos = -1;    // 最后一个不可能作为起点的位置
                int cnt[2] = {0, 0};
                int l = 0;
    
                for (int r = 0; r < n; ++r) {
                    // 扩展右端点
                    ++cnt[s[r] - '0'];
    
                    // 收缩左端点，使窗口尽量短且保持“潜在合法”
                    for (; l < r; ++l) {
                        if (s[l] == '0' && cnt[0] > zero) {
                            // 多余的 0，必须去掉
                            --cnt[0];
                            lastInvalidPos = l;  // 以 <= l 为起点都不合法
                        } else if (s[l] == '1' && cnt[1] - 1 >= zero * zero) {
                            // 1 还富裕，可以扔掉一个 1，使窗口更短
                            --cnt[1];
                        } else {
                            // 再删就会破坏“0 == zero or 1 >= zero^2”的可能性
                            break;
                        }
                    }
    
                    // 当前窗口 [l, r] 中 0 的个数刚好为 zero，且 1 的个数 >= zero^2
                    if (cnt[0] == zero && cnt[1] >= zero * zero) {
                        // 所有起点 L ∈ [lastInvalidPos+1, l] 都是合法起点
                        ans += (l - lastInvalidPos);
                    }
                }
            }
    
            return (int)ans;
        }
    };

int main() {
    Solution solution;
    string s = "00011";
    cout << solution.numberOfSubstrings(s) << endl;

    Solution2 solution2;
    cout << solution2.numberOfSubstrings(s) << endl;
    return 0;
}