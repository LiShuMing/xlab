#include "../include/fwd.h"

class Solution {
public:
    int bestTiming(vector<int>& prices) {
        int n = prices.size();
        int max_profit = 0;
        // for (int i = 0; i < n; i++) {
        //     for (int j = i + 1; j < n; j++) {
        //         max_profit = max(max_profit, prices[j] - prices[i]);
        //     }
        // }
        // return max_profit;

        // use dynamic programming
        vector<vector<int>> dp(n, vector<int>(2, 0));
        dp[0][0] = 0;
        dp[0][1] = -prices[0];
        for (int i = 1; i < n; i++) {
            dp[i][0] = max(dp[i - 1][0], dp[i - 1][1] + prices[i]);
            dp[i][1] = max(dp[i - 1][1], -prices[i]);
        }
        return dp[n - 1][0];
    }
};
int main() {
    Solution solution;
    vector<int> prices = {7, 1, 5, 3, 6, 4};
    cout << solution.bestTiming(prices) << endl;
    return 0;
}