#include "../include/fwd.h"

class Solution {
public:
    int solve(string s, int k, int l, int r) {
        if (l > r) {
            return 0;
        }
        // TODO: use std::array to optimize the time complexity
        unordered_map<char, int> cnt;
        for (int i = l; i <= r; i++) {
            cnt[s[i]]++;
        }
        for (int i = l; i <= r; i++) {
            if (cnt[s[i]] < k) {
                return max(solve(s, k, l, i - 1), solve(s, k, i + 1, r));
            }
        }
        return r - l + 1;
    }
    int longestSubstring(string s, int k) {
        return solve(s, k, 0, s.size() - 1);
    }
};

int main() {
    Solution solution;
    string s = "aaabb";
    int k = 3;
    cout << solution.longestSubstring(s, k) << endl;
    return 0;
}