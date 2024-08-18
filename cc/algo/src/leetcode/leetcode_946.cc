#include "../include/fwd.h"

class Solution {
public:
    bool validateStackSequences(vector<int>& pushed, vector<int>& popped) {
        stack<int> s;
        int i = 0;
        int j = 0;
        while (j < popped.size()) {
            if (!s.empty() && s.top() == popped[j]) {
                s.pop();
                j++;
            } else if (i < pushed.size()) {
                s.push(pushed[i]);
                i++;
            } else {
                return false;
            }
        }
        return true;
    }
};
int main() {
    Solution solution;
    vector<int> pushed = {1, 2, 3, 4, 5};
    vector<int> popped = {4, 5, 3, 2, 1};
    cout << "pushed: " << strJoin(pushed, " ") << endl;
    cout << "popped: " << strJoin(popped, " ") << endl;
    cout << "validateStackSequences: " << solution.validateStackSequences(pushed, popped) << endl;
    return 0;
}