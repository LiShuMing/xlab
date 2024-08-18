#include "../include/fwd.h"

class Solution {
public:
    long long maxMatrixSum(vector<vector<int>>& matrix) {
        int m = matrix.size();
        int n = matrix[0].size();
        long long ans = 0;
        int min_val = INT_MAX;
        int negative_count = 0;
        for (int i = 0; i < m; i++) {
            for (int j = 0; j < n; j++) {
                if (matrix[i][j] < 0) {
                    negative_count++;
                }
                ans += abs(matrix[i][j]);
                min_val = min(min_val, abs(matrix[i][j]));
            }
        }
        if (negative_count % 2 == 0) {
            return ans;
        } else {
            return ans - 2 * min_val;
        }
    }
};

int main() {
    Solution solution;
    vector<vector<int>> matrix = {{1, 2, 3}, {4, 5, 6}, {7, 8, 9}};
    cout << solution.maxMatrixSum(matrix) << endl;
    return 0;
}