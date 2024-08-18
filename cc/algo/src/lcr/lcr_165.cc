#include "../include/fwd.h"

class Solution {
public:
    int crackNumber(int ciphertext) {
        string s = to_string(ciphertext);
        int n = s.size();
        if (n == 0) return 1;

        // dp[i] represents the number of ways to decode the first i characters
        vector<int> dp(n + 1, 0);
        dp[0] = 1; // one way to decode empty string
        dp[1] = 1; // one way to decode the first character

        for (int i = 2; i <= n; i++) {
            string twoDigits = s.substr(i - 2, 2);
            // Check if first digit is not '0' (two-digit numbers can't start with 0)
            int num = stoi(twoDigits);
            if (num >= 10 && num <= 25) {
                dp[i] = dp[i - 1] + dp[i - 2];
            } else {
                dp[i] = dp[i - 1];
            }
        }
        return dp[n];
    }
};
int main() {
    Solution solution;
    cout << solution.crackNumber(216612) << endl;
    cout << solution.crackNumber(220) << endl;
    return 0;
}