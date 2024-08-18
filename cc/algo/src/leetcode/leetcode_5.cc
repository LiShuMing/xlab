#include "../include/fwd.h"

class Solution {
public:
    string longestPalindrome(string s) {
        int n = s.size();
        vector<vector<bool>> dp(n, vector<bool>(n, false));
        int ans = 0;
        string ans_str = "";
        for (int i = 0; i < n; i++) {
            for (int j = 0; j <= i; j++) {
                if (i == j) {
                    dp[j][i] = true;
                } else if (i == j + 1) {
                    dp[j][i] = s[i] == s[j];
                } else {
                    dp[j][i] = dp[j + 1][i - 1] && s[i] == s[j];
                }
                if (dp[j][i]) {
                    if (i - j + 1 > ans) {
                        ans = i - j + 1;
                        ans_str = s.substr(j, i - j + 1);
                    }
                }
            }
        }
        return ans_str;
    }
};
int main() {
    Solution solution;
    string s = "babad";
    cout << solution.longestPalindrome(s) << endl;
    return 0;
}