#include "../include/fwd.h"

class Solution {
public:
    int maxOperations(string s) {
        int ans = 0;
        int n = s.size();
        int i = n - 1;
        int k = 0;
        while (i >= 0) {
            if (s[i] == '1') {
                while (i >= 0 && s[i] == '1') {
                    ans += k;
                    i--;
                }
            } else {
                while (i >= 0 && s[i] == '0') {
                    i--;
                }
                k++;
            }
        }
        return ans;
    }
};
int main() {
    Solution sol;
    string s = "1001101";
    cout << sol.maxOperations(s) << endl;
    return 0;
}