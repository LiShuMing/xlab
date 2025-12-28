#include "../include/fwd.h"

/**
Given strings s1 and s2, return the minimum (contiguous) substring part of s1 such that s2 is a subsequence of the part.

If there is no such window in s1 that covers all characters in s2 in the right order, return the empty string.

If there are multiple such minimum-length windows, return the one with the leftmost starting index.

Example 1:
Input: s1 = "abcdebdde", s2 = "bde"
Output: "bcde"
Explanation: 
"bcde" is the answer because it occurs before "bdde" which has the same length.
"bcde" is the substring of s1 that contains "b", "d", and "e" in order.

Example 2:
Input: s1 = "jmeqksfrsdcmsiwvaovztaqenprpvnbstl", s2 = "u"
Output: ""

Constraints:
1 <= s1.length <= 2 * 10^4
1 <= s2.length <= 100
s1 and s2 consist of lowercase English letters.
 */
class Solution {
public:
    string minWindow(string s, string t) {
        int n = s.size();
        int m = t.size();
        if (m > n) {
            return "";
        }
        // fast check, if all characters in t are in s, return the whole s
        for (char c : t) {
            if (s.find(c) == string::npos) {
                return "";
            }
        }
        // use two pointers to find the minimum window
        int l = 0;
        int r = m - 1;
        int ans = n + 1;
        int start = 0;
        while (l <= r && l < n && r < n) {
            // check if s[r] is in t
            if (t.find(s[l]) != string::npos) {
                // check if the window is valid
                if (isSubsequence(s, t, l, l + m - 1)) {
                    ans = min(ans, r - l + 1);
                    start = l;
                }
                l++;
            }
            r++;
        }
        return s.substr(start, ans);
    }
    bool isSubsequence(const string& s, const string& t, int l, int r) {
        // check if t is a subsequence of s[l:r+1]
        int i = 0;
        int j = 0;
        while (i <= r && j < t.size()) {
            if (s[i] == t[j]) {
                j++;
            }
            i++;
        }
        return j == t.size();
    }
};
int main() {
    Solution solution;
    string s = "ADOBECODEBANC";
    string t = "ABC";
    cout << solution.minWindow(s, t) << endl;
    return 0;
}