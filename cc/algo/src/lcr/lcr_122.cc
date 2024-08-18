#include "../include/fwd.h"
class Solution {
public:
    string pathEncryption(string path) {
        int n = path.size();
        string ans;
        for (int i = 0; i < n; i++) {
            if (path[i] == '/') {
                ans.push_back('a');
            } else {
                ans.push_back(path[i]);
            }
        }
        return ans;
    }
};
int main() {
    Solution solution;
    string path = "/a/b/c";
    string ans = solution.pathEncryption(path);
    cout << ans << endl;
    return 0;
}