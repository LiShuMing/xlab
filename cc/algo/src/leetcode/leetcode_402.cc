#include "../include/fwd.h"

class Solution {
public:
    string removeKdigits(string num, int k) {
        stack<char> s;
        for (char c : num) {
            while (!s.empty() && s.top() > c && k > 0) {
                s.pop();
                k--;
            } 
            s.push(c);
        }
        while (!s.empty() && k > 0) {
            s.pop();
            k--;
        }
        string result;
        while (!s.empty()) {
            result.push_back(s.top());
            s.pop();
        }
        reverse(result.begin(), result.end());
        while (result.size() > 1 && result[0] == '0') {
            result.erase(0, 1);
        }
        return result == "" ? "0" : result;
    }
};
int main() {
    Solution solution;
    string num = "1432219";
    int k = 3;
    cout << "num: " << num << endl;
    cout << "k: " << k << endl;
    cout << "removeKdigits: " << solution.removeKdigits(num, k) << endl;
    return 0;
}