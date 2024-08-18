#include "../include/fwd.h"

class Solution {
public:
    int countSubstrings(string s) {
        int n = s.size();
        vector<vector<bool> > dp(n, vector<bool>(n, false));
        int ans = 0;
        
        for (int i = 0; i < n; i++) {
            for (int j = 0; j <= i; j++) {
                if (i == j) {
                    // Single character is always a palindrome
                    dp[j][i] = true;
                    ans++;
                } else if (i == j + 1) {
                    // Two characters: palindrome if they are equal
                    if (s[i] == s[j]) {
                        dp[j][i] = true;
                        ans++;
                    }
                } else {
                    // More than two characters: palindrome if first and last are equal
                    // and the substring between them is also a palindrome
                    if (s[i] == s[j] && dp[j + 1][i - 1]) {
                        dp[j][i] = true;
                        ans++;
                    }
                }
            }
        }
        return ans;
    }
};

int main() {
    Solution solution;
    string s = "abc";
    cout << solution.countSubstrings(s) << endl;
    s = "aaa";
    cout << solution.countSubstrings(s) << endl;
    s = "aaaa";
    cout << solution.countSubstrings(s) << endl;
    s = "aaaaa";
    cout << solution.countSubstrings(s) << endl;
    s = "aaaaaa";
    cout << solution.countSubstrings(s) << endl;
    s = "aaaaaaa";
    cout << solution.countSubstrings(s) << endl;
    s = "aaaaaaaa";
    cout << solution.countSubstrings(s) << endl;
    return 0;
}