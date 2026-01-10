#include "../include/fwd.h"

class Solution {
    public:
        long long maxProfit(vector<int>& prices, vector<int>& strategy, int k) {
            int n = prices.size();
            vector<long long> profit_sum(n + 1, 0);
            vector<long long> price_sum(n + 1, 0);
            for (int i = 0; i < n; i++) {
                profit_sum[i + 1] = profit_sum[i] + prices[i] * strategy[i];
            }
            long long ans = profit_sum[n];
            for (int i = k - 1; i < n; i++) {
                long long left_profit = profit_sum[i - k + 1];
                long long right_profit = profit_sum[n] - profit_sum[i + 1];
                long long change_profit = price_sum[i + 1] - price_sum[i - k / 2 + 1];
                ans = max(ans, left_profit + right_profit + change_profit);
            }
            return ans;
        }
    };