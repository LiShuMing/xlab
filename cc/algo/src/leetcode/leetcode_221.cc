#include "../include/fwd.h"

class Solution {
public:
    int maximalSquare(vector<vector<char>>& matrix) {
        if (matrix.empty()) return 0;
        int n = matrix.size();
        int m = matrix[0].size();
        if (n == 0 || m == 0) return 0;
        vector<vector<int>> dp(n, vector<int>(m, 0));
        int ans = 0;
        for (int i = 0; i < n; i++) {
            for (int j = 0; j < m; j++) {
                if (matrix[i][j] == '1') {
                    if (i == 0 || j == 0) {
                        dp[i][j] = 1;
                    } else {
                        dp[i][j] = min(dp[i-1][j], min(dp[i][j-1], dp[i-1][j-1])) + 1;
                    }
                    ans = max(ans, dp[i][j]);
                }
            }
        }
        return ans * ans;
    }
};
int main() {
    Solution solution;
    vector<vector<char>> matrix = {{'1', '0', '1', '0', '0'}, {'1', '0', '1', '1', '1'}, {'1', '1', '1', '1', '1'}, {'1', '0', '0', '1', '0'}};
    cout << solution.maximalSquare(matrix) << endl;
    return 0;
}