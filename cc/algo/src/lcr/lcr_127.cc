#include "../include/fwd.h"
class Solution {
public:
    int trainWays(int num) {
        if (num == 0) return 1;
        if (num == 1) return 1;
        vector<int> dp = vector<int>(num + 1, 0);
        dp[0] = 1;
        dp[1] = 1;
        for (int i = 2; i <= num; i++) {
            dp[i] = (dp[i - 1] + dp[i - 2]) % static_cast<int>(1e9 + 7);
        }
        return dp[num] % static_cast<int>(1e9 + 7);
    }
};
int main() {
    Solution solution;
    cout << solution.trainWays(10) << endl;
    return 0;
}