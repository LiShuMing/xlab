#include "../include/fwd.h"
class Solution {
public:
    vector<double> statisticsProbability(int num) {
        // dp[i] represents probability of getting sum i
        vector<double> dp(6, 1.0/6.0);
        
        for (int i = 2; i <= num; i++) {
            // For i dice, possible sums range from i to 6*i
            vector<double> tmp(5 * i + 1, 0);
            
            for (int j = 0; j < dp.size(); j++) {
                for (int k = 0; k < 6; k++) {
                    tmp[j + k] += dp[j] * 1.0/6.0;
                }
            }
            dp = tmp;
        }
        return dp;
    }
};

int main() {
    Solution solution;
    vector<double> ans = solution.statisticsProbability(1);
    printVector(ans);
    return 0;
}