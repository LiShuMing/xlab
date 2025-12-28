#include "../include/fwd.h"

class Solution {
public:
    vector<string> generateParenthesis(int n) {
        vector<string> ans;
        string current;
        backtrack(ans, current, 0, 0, n);
        return ans;
    }
    void backtrack(vector<string>& ans, string& current, int open, int close, int n) {
        if (current.size() == 2 * n) {
            ans.push_back(current);
            return;
        }
        if (open < n) {
            current.push_back('(');
            backtrack(ans, current, open + 1, close, n);
            current.pop_back();
        }
        if (close < open) {
            current.push_back(')');
            backtrack(ans, current, open, close + 1, n);
            current.pop_back();
        }
    }
};

int main() {
    Solution solution;
    int n = 3;
    vector<string> ans = solution.generateParenthesis(n);
    for (const auto& s : ans) {
        cout << s << endl;
    }
    return 0;
}