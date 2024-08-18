#include "../include/fwd.h"

// Longest Repeating Character Replacement
// Sliding window with "maxCount" trick.
// Time: O(n), Space: O(1).
class Solution {
public:
    int characterReplacement(const string& s, int k) {
        int n = s.size();
        int ans = 0;
        int l = 0;
        int r = 0;
        int maxCount = 0;
        array<int, 26> cnt;
        cnt.fill(0);
        while (r < n) {
            cnt[s[r] - 'A']++;
            maxCount = max(maxCount, cnt[s[r] - 'A']);
            while (r - l + 1 - maxCount > k) {
                cnt[s[l] - 'A']--;
                l++;
            }
            ans = max(ans, r - l + 1);
            r++;
        }
        return ans;
    }
};

int main() {
    Solution solution;
    string s = "AABABBA";
    int k = 1;
    cout << solution.characterReplacement(s, k) << endl;
    return 0;
}