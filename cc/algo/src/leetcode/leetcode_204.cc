#include "../include/fwd.h"

class Solution {
public:
    vector<int> findAnagrams(string s, string p) {
        int n = s.size(), m = p.size();
        vector<int> ans;
        vector<int> cnt(26);
        for (char c : p) cnt[c - 'a']++;
        for (int i = 0; i < n; i++) {
            cnt[s[i] - 'a']--;
            if (i >= m) cnt[s[i - m] - 'a']++;
            if (all_of(cnt.begin(), cnt.end(), [](int x) { return x == 0; })) {
                ans.push_back(i - m + 1);
            }
        }
        return ans;
    }
};
