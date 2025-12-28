#include "../include/fwd.h"

class Solution {
public:
    int jewelleryValue(vector<vector<int>>& frame) {
        if (frame.empty()) return 0;
        int n = frame.size();
        int m = frame[0].size();
        vector<vector<int>> dp(n, vector<int>(m, 0));
        dp[0][0] = frame[0][0];
        for (int i = 1; i < n; i++) {
            dp[i][0] = dp[i - 1][0] + frame[i][0];
        }
        for (int j = 1; j < m; j++) {
            dp[0][j] = dp[0][j - 1] + frame[0][j];
        }

        for (int i = 1; i < n; i++) {
            for (int j = 1; j < m; j++) {
                dp[i][j] = max(dp[i][j], dp[i - 1][j] + frame[i][j]);
                dp[i][j] = max(dp[i][j], dp[i][j - 1] + frame[i][j]);
            }
        }
        return dp[n - 1][m - 1];
    }
};

int main() {
    Solution solution;
    vector<vector<int>> frame = {{1, 2, 3}, {4, 5, 6}, {7, 8, 9}};
    cout << solution.jewelleryValue(frame) << endl;
    return 0;
}