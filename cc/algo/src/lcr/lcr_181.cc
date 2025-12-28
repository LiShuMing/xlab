#include "../include/fwd.h"

class Solution {
public:
    string reverseMessage(string message) {
        int n = message.size();
        int r = n - 1;
        while (r >= 0 && message[r] == ' ') r--;
        int l = 0;
        while (l < r && message[l] == ' ') l++;
        int i = r;
        string ans = "";
        while (i >= l) {
            if (message[i] == ' ') {
                ans += message.substr(i + 1, r - i) + " ";
                while (i >= l && message[i] == ' ') i--;
                r = i;
            } 
            if (i == l) {
                ans += message.substr(i, r - i + 1);
                break;
            }
            cout << "i: " << i << ", l: " << l << ", r: " << r << ", ans: " << ans << endl;
            i--;
        }
        return ans;
    }
};

int main() {
    Solution solution;
    cout << solution.reverseMessage("the sky is blue") << endl;
    cout << solution.reverseMessage("a good   example ") << endl;
    return 0;
}