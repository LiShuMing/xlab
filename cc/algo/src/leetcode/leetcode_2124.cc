#include "../include/fwd.h"

class Solution {
public:
    bool checkStrictlyIncreasing(string s) {
        int n = s.size();
        for (int i = 1; i < n; i++) {
            if (s[i - 1] > s[i]) return false;
        }
        return true;
    }
};

int main() {
    string s = "leetcode";
    Solution sol;
    cout << sol.checkStrictlyIncreasing(s) << endl;
    return 0;
}