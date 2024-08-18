#include "../include/fwd.h"

/**
* Given a binary string s and an integer k, return true if all binary codes of length k are a substring of s. Otherwise, return false.
* 
* Example 1:
* Input: s = "00110110", k = 2
* Output: true
* Explanation: The binary codes of length 2 are "00", "01", "10" and "11". They can be all found as substrings in s.
* 
* Example 2:
* Input: s = "0110", k = 2
* Output: false
* Explanation: The binary codes of length 2 are "00", "01", "10" and "11". "00" is missing from s.
* 
* Example 3:
* Input: s = "0110", k = 3
* Output: false
* Explanation: The binary codes of length 3 are "000", "001", "010", "011", "100", "101", "110" and "111". They can be all found as substrings in s.
 */
class Solution {
public:
    bool hasAllCodes(string s, int k) {
        int n = s.size();
        int need = 1 << k;
        if (n < k || n - k + 1 < need) {
            return false;
        }
        vector<bool> seen(need, false);
        int val = 0;
        for (int i = 0; i < k; i++) {
            val = (val << 1) | (s[i] - '0');
        }
        int cnt = 1;
        seen[val] = true;
        int mask = need - 1;
        for (int i = k; i < n; i++) {
            val = ((val << 1) | (s[i] - '0')) & mask;
            if (!seen[val]) {
                seen[val] = true;
                if (++cnt == need) return true;
            }
        }
        return cnt == need;
    }
};

int main() {
    Solution solution;
    cout << solution.hasAllCodes("00110110", 2) << endl;  // true
    cout << solution.hasAllCodes("0110", 2) << endl;      // false
    return 0;
}