#include "../include/fwd.h"
class Solution {
public:
    int maxSideLength(vector<vector<int>>& mat, int threshold) {
        int m = mat.size();
        int n = mat[0].size();

        vector<vector<int>> prefixSum(m + 1, vector<int>(n + 1, 0));
        for (int i = 1; i <= m; i++) {
            for (int j = 1; j <= n; j++) {
                prefixSum[i][j] = prefixSum[i - 1][j] + prefixSum[i][j - 1] -
                                  prefixSum[i - 1][j - 1] + mat[i - 1][j - 1];
            }
        }
        auto check = [&](int k) -> bool {
            for (int i = k; i <= m; i++) {
                for (int j = k; j <= n; j++) {
                    int sum = prefixSum[i][j] - prefixSum[i - k][j] - prefixSum[i][j - k] + prefixSum[i - k][j - k];
                    if (sum <= threshold) {
                        return true;
                    }
                }
            }
            return false;
        };
        int left = 1;
        int right = min(m, n);
        int ans = 0;
        while (left <= right) {
            int mid = left + (right - left) / 2;
            if (check(mid)) {
                ans = mid;
                left = mid + 1;
            } else {
                right = mid - 1;
            }
        }
        return ans;
    }
};

int main() {
    Solution solution;
    vector<vector<int>> mat = {{1, 1, 3, 2, 4, 3, 2}, {1, 1, 3, 2, 4, 3, 2}, {1, 1, 3, 2, 4, 3, 2}};
    int threshold = 4;
    cout << solution.maxSideLength(mat, threshold) << endl;
    return 0;
}