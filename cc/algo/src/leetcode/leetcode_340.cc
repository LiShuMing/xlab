#include "../include/fwd.h"

class Solution {
public:
    // Longest substring with at most k distinct characters.
    // Time: O(n), Space: O(1) for ASCII (fixed 256 array).
    int lengthOfLongestSubstringKDistinct(string s, int k) {
        if (k == 0) {
            return 0;
        }
        int n = s.size();
        int ans = 0;
        unordered_map<char, int> cnt;
        int l = 0;
        for (int i = 0; i < n; i++) {
            cnt[s[i]]++;
            while (cnt.size() > k) {
                cnt[s[l]]--;
                if (cnt[s[l]] == 0) {
                    cnt.erase(s[l]);
                }
                l++;
            }
            ans = max(ans, i - l + 1);
        }
        return ans;
    }
};

int main() {
    Solution solution;
    string s = "eceba";
    int k = 2;
    cout << solution.lengthOfLongestSubstringKDistinct(s, k) << endl;
    return 0;
}   