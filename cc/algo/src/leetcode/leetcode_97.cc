#include "../include/fwd.h"
class Solution {
public:
    bool isInterleave(string s1, string s2, string s3) {
        int m = s1.size();
        int n = s2.size();
        int k = s3.size();
        if (m + n != k) return false;
        vector<vector<bool>> dp(m + 1, vector<bool>(n + 1, false));
        dp[0][0] = true;
        for (int i = 0; i <= m; i++) {
            for (int j = 0; j <= n; j++) {
                if (i == 0 && j == 0) continue;
                if (i == 0) {
                    dp[i][j] = dp[i][j-1] && s2[j-1] == s3[i+j-1];
                } else if (j == 0) {
                    dp[i][j] = dp[i-1][j] && s1[i-1] == s3[i+j-1];
                } else {
                    dp[i][j] = (dp[i-1][j] && s1[i-1] == s3[i+j-1]) || (dp[i][j-1] && s2[j-1] == s3[i+j-1]);
                }
            }
        }
        return dp[m][n];
    }
};

int main() {
    Solution solution;
    string s1 = "aabcc";
    string s2 = "dbbca";
    string s3 = "aadbbcbcac";
    cout << solution.isInterleave(s1, s2, s3) << endl;
    return 0;
}