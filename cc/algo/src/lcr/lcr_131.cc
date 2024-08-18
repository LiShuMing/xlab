#include "../include/fwd.h"
class Solution {
public:
    int cuttingBamboo(int bamboo_len) {
        vector<int> dp(bamboo_len + 1, 0);
        for (int i = 2; i <= bamboo_len; i++) {
            for (int j = 1; j < i; j++) {
                dp[i] = max(dp[i], max(j * (i - j), j * dp[i - j]));
            }
        }
        return dp[bamboo_len];
    }
};
int main() {
    Solution solution;
    cout << solution.cuttingBamboo(5) << endl;
    return 0;
}