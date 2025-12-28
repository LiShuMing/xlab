#include "../include/fwd.h"

class Solution {
public:
    int longestIncreasingPath(vector<vector<int>>& matrix) {
        int n = matrix.size();
        int m = matrix[0].size();
        vector<vector<int>> dp(n, vector<int>(m, 0));
        int ans = 0;
        for (int i = 0; i < n; i++) {
            for (int j = 0; j < m; j++) {
                ans = max(ans, dfs(matrix, i, j, dp));
            }
        }
        return ans;
    }
    int dfs(vector<vector<int>>& matrix, int i, int j, vector<vector<int>>& dp) {
        if (dp[i][j] != 0) return dp[i][j];
        int n = matrix.size();
        int m = matrix[0].size();
        int max_path = 1;
        if (i > 0 && matrix[i][j] < matrix[i - 1][j]) {
            max_path = max(max_path, dfs(matrix, i - 1, j, dp) + 1);
        }
        if (i < n - 1 && matrix[i][j] < matrix[i + 1][j]) {
            max_path = max(max_path, dfs(matrix, i + 1, j, dp) + 1);
        }
        if (j > 0 && matrix[i][j] < matrix[i][j - 1]) {
            max_path = max(max_path, dfs(matrix, i, j - 1, dp) + 1);
        }
        if (j < m - 1 && matrix[i][j] < matrix[i][j + 1]) {
            max_path = max(max_path, dfs(matrix, i, j + 1, dp) + 1);
        }
        dp[i][j] = max_path;
        return max_path;
    }
};

int main() {
    Solution solution;
    vector<vector<int>> matrix = {{1, 2, 3}, {4, 5, 6}, {7, 8, 9}};
    cout << solution.longestIncreasingPath(matrix) << endl;
    return 0;
}