#include "../include/fwd.h"


class Solution {
public:
    string findLongestWord(string s, vector<string>& dictionary) {
        int n = s.size();
        for (string& t : dictionary) {
            int r = 0;
            for (int i = 0; i < n; i++) {
                while (r < t.size() && s[i] != t[r]) {
                    i++;
                }
            }
        }
    }
};
