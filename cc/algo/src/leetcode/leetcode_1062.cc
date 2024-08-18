#include "../include/fwd.h"
/**
Given a string s, return the length of the longest repeating substring(s). 
If no repeating substring exists, return 0.

Example 1:
Input: s = "abcd"
Output: 0
Explanation: There is no repeating substring.

Example 2:
Input: s = "abbaba"
Output: 2
Explanation: The longest repeating substrings are "ab" and "ba", each of which occurs twice.

Example 3:
Input: s = "aabcaabdaab"
Output: 3
Explanation: The longest repeating substring is "aab", which occurs 3 times.

Constraints:
1 <= s.length <= 1500
s consists of lowercase English letters only.
 */


class Solution {
public:
    int longestRepeatingSubstring(string s) {
        int n = s.size();
        int l = 0;
        int r = n - 1;
        int ans = 0;
        while (l <= r) {
            int mid = (l + r) / 2;
            if (hasRepeatingSubstring(s, mid)) {
                ans = mid;
                l = mid + 1;
            } else {
                r = mid - 1;
            }
        }
        return ans;
    }
    bool hasRepeatingSubstring(string s, int len) {
        unordered_set<string> st;
        for (int i = 0; i + len <= s.size(); i++) {
            string sub = s.substr(i, len);
            if (st.find(sub) != st.end()) {
                return true;
            }
            st.insert(sub);
        }
        return false;
    }

    int longestRepeatingSubstringV2(string s) {
        // Suffix Array Solution:
        // 1. Build suffix array: a vector<int> storing the starting index of each suffix, sorted by suffix.
        // 2. Compute the LCP array (Longest Common Prefix): for each pair of consecutive suffixes, compute the number of leading characters they share.
        // 3. The answer is the maximum value in the LCP array.

        int n = s.size();
        vector<int> suffixArray(n);
        for (int i = 0; i < n; ++i) suffixArray[i] = i;
        
        // Optimized comparison: compare suffixes without creating substrings
        sort(suffixArray.begin(), suffixArray.end(), [&](int a, int b) {
            // Compare suffixes starting at indices a and b
            int len = min(n - a, n - b);
            for (int i = 0; i < len; ++i) {
                if (s[a + i] != s[b + i]) {
                    return s[a + i] < s[b + i];
                }
            }
            // If one is a prefix of the other, shorter comes first
            return (n - a) < (n - b);
        });
        // print the suffix array
        for (int i = 0; i < n; ++i) {
            cout << s.substr(suffixArray[i], n - suffixArray[i]) << " ";
        }
        cout << endl;

        // Compute LCP array: LCP[i] = longest common prefix of s.substr(suffixArray[i]) and s.substr(suffixArray[i-1])
        int ans = 0;
        for (int i = 1; i < n; ++i) {
            int a = suffixArray[i-1];
            int b = suffixArray[i];
            int lcp = 0;
            while (a + lcp < n && b + lcp < n && s[a + lcp] == s[b + lcp]) {
                ++lcp;
            }
            ans = max(ans, lcp);
        }
        return ans;
    }
};
int main() {
    Solution solution;
    vector<string> strs = {"abcd", "abbaba", "aabcaabdaab"};
    for (auto& s : strs) {
        cout << solution.longestRepeatingSubstring(s) << endl;
        cout << solution.longestRepeatingSubstringV2(s) << endl;
    }
    return 0;
}