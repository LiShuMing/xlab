#include "../include/fwd.h"

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

        unordered_map<char, int> exp;
        for (char c : t) {
            exp[c]++;
        }

        unordered_map<char, int> act;
        int l = 0, r = 0, start = 0, len = INT_MAX;
        
        // Expand window by moving right boundary
        for (r = 0; r < n; r++) {
            act[s[r]]++;
            
            // Try to shrink window by moving left boundary
            // Keep shrinking while window still satisfies the condition
            while (check_func(act, exp) && l <= r) {
                // Update minimum window if current window is smaller
                if (r - l + 1 < len) {
                    start = l;
                    len = r - l + 1;
                }
                // Remove leftmost character and move left boundary
                act[s[l]]--;
                l++;
            }
        }
        
        return len == INT_MAX ? "" : s.substr(start, len);
    }
    bool check_func(unordered_map<char, int>& act, unordered_map<char, int>& exp) const {
        for (auto& [ch, cnt_val]: exp) {
            if (act.find(ch) == act.end() || act.at(ch) < cnt_val) {
                return false;
            }
        }
        return true;
    }
};

int main() {
    Solution solution;
    string s = "ADOBECODEBANC";
    string t = "ABC";
    cout << solution.minWindow(s, t) << endl;
    return 0;
}