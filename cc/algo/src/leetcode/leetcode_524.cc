#include "../include/fwd.h"


class Solution {
public:
    string findLongestWord(string s, vector<string>& dictionary) {
        int n = s.size();
        string ans;
        for (string& t : dictionary) {
            // r: index of t
            int r = 0;
            for (int i = 0; i < n; i++) {
                if (s[i] == t[r]) {
                    r++;
                }
            }
            if (r == t.size()) {
                if (t.size() > ans.size() || (t.size() == ans.size() && t < ans)) {
                    ans = t;
                }
            }
        }
        return ans;
    }
};
