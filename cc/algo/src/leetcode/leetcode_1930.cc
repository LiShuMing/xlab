#include "../include/fwd.h"

class Solution {
public:
    int countPalindromicSubsequence(string s) {
        int ans = 0;
        for (char apha = 'a'; apha <= 'z'; apha++) {
            int first = s.find(apha);
            int last = s.rfind(apha);
            if (first == string::npos || last == string::npos) {
                continue;
            }
            int count[26] = {0};
            for (int i = first + 1; i < last; i++) {
                if (count[s[i] - 'a'] == 0) {
                    ans++;
                }
                count[s[i] - 'a']++;
            }
        }
        return ans;
    }
};

int main() {
    Solution solution;
    // case 1
    // string s = "aabca";
    // case 2
    vector<string> strs = {"adc", "aabca", "bbcbaba"}  ;
    for (auto& s : strs) {
        int ans = solution.countPalindromicSubsequence(s);
        cout << ans << endl;
    }
    return 0;
}