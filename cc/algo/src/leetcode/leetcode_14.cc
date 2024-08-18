#include "../include/fwd.h"

class Solution {
public:
    string longestCommonPrefix(vector<string>& strs) {
        if (strs.empty()) {
            return "";
        }
        string prefix = strs[0];
        for (int i = 1; i < strs.size(); i++) {
            while (strs[i].find(prefix) != 0) {
                prefix = prefix.substr(0, prefix.size() - 1);
            }
        }
        return prefix;
    }
};
int main() {
    Solution solution;
    vector<string> strs = {"flower", "flow", "flight"};
    cout << solution.longestCommonPrefix(strs) << endl;
    return 0;
}