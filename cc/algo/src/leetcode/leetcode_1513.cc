#include "../include/fwd.h"

class Solution {
private:
    static const int MOD = 1e9 + 7;
public:
    int numSub(string s) {
        int n = s.size();
        int ans = 0;
        for (int i = 0, l = 0; i < n; i++) {
            if (s[i] == '0') continue;
            l = i;
            while (++i < n && s[i] == '1') {
            }
            ans = (ans + factorial(i - l)) % MOD;
        }
        return ans;
    }

    int factorial(int n) {
        return (long long)n * (n + 1) / 2 % MOD;
        // cout << "factorial(" << n << ")" << endl;
        // if (n == 0) return 1;
        // int ans = 1;
        // for (int i = 1; i <= n; i++) {
        //     ans = (ans * i) % MOD;
        // }
        // return ans;
    }
};
int main() {
    Solution solution;
    string s = "00011";
    cout << solution.numSub(s) << endl;
    s = "111111";
    cout << solution.numSub(s) << endl;
    s = "000000";
    cout << solution.numSub(s) << endl;
    s = "100000";
    cout << solution.numSub(s) << endl;
    s = "010000";
    cout << solution.numSub(s) << endl;
    return 0;
}