#include "../include/fwd.h"
class Solution {
private:
    static const int MOD = 1e9 + 7; 
public:
    int numOfWays(int n) {
        // vector<vector<int>> dp(n, vector<int>(3));
        // dp[0][0] = 6;
        // dp[0][1] = 6;
        // dp[0][2] = 6;
        // for (int i = 1; i < n; i++) {
        //     dp[i][0] = (dp[i-1][0] * 2 + dp[i-1][1] * 1 + dp[i-1][2] * 1) % MOD;
        //     dp[i][1] = (dp[i-1][0] * 1 + dp[i-1][1] * 2 + dp[i-1][2] * 1) % MOD;
        //     dp[i][2] = (dp[i-1][0] * 1 + dp[i-1][1] * 1 + dp[i-1][2] * 2) % MOD;
        // }
        // return (dp[n-1][0] + dp[n-1][1] + dp[n-1][2]) % MOD;

        int fi0 = 6, fi1 = 6;
        for (int i = 2; i <= n; i++) {
            int new_fi0 = (2LL * fi0 + 2LL * fi1) % MOD;
            int new_fi1 = (2LL * fi0 + 3LL * fi1) % MOD;
            fi0 = new_fi0;
            fi1 = new_fi1;
        }
        return (fi0 + fi1) % MOD;
    }
};