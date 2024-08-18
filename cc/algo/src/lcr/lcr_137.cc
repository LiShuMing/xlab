#include "../include/fwd.h"

class Solution {
public:
    bool articleMatch(string s, string p) {
        int m = s.size(), n = p.size();
        vector<vector<bool>> dp(m + 1, vector<bool>(n + 1, false));
        dp[0][0] = true;
        // Initialize dp[0][j] for patterns like a*, a*b*, etc.
        for (int i = 0; i <= m; i++) {
            for (int j = 0; j <= n; j++) {
                if (j == 0) {
                    dp[i][j] = i == 0;
                } else {
                    if (p[j - 1] == '*') {
                        if (j >= 2) {
                            dp[i][j] = dp[i][j - 2];
                        }
                        if (i >= 1 && (p[j - 2] == s[i - 1] || p[j - 2] == '.')) {
                            dp[i][j] = dp[i][j] || dp[i - 1][j];
                        }
                    } else {
                        if (i >= 1 && j >= 1 && (p[j - 1] == '.' || s[i - 1] == p[j - 1])) {
                            dp[i][j] = dp[i - 1][j - 1];
                        }
                    }
                }
            }
        }
        return dp[m][n];
    }
};
int main() {
    Solution solution;
    cout << solution.articleMatch("aab", "c*a*b") << endl;
    cout << solution.articleMatch("aa", "a") << endl;
    return 0;
}