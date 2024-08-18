#include "../include/fwd.h"
class Solution {
public:
    vector<int> countNumbers(int cnt) {
        vector<int> ans;
        backtrack(ans, cnt, 0);
        return ans;
    }
    void backtrack(vector<int>& ans, int cnt, int num) {
        if (cnt == 0) {
            if (num == 0) return;
            ans.push_back(num);
            return;
        }
        for (int i = 0; i < 10; i++) {
            //if (num == 0 && i == 0) continue;
            backtrack(ans, cnt - 1, num * 10 + i);
        }
    }
    // vector<int> countNumbers(int cnt) {
    //     int max_num = pow(10, cnt) - 1;
    //     vector<int> ans;
    //     for (int i = 1; i <= max_num; i++) {
    //         ans.push_back(i);
    //     }
    //     return ans;
    // }
};
int main() {
    Solution solution;
    auto ans = solution.countNumbers(2);
    printVector(ans);
    // ans = solution.countNumbers(3);
    // printVector(ans);
    // ans = solution.countNumbers(4);
    // printVector(ans);
    // ans = solution.countNumbers(5);
    // printVector(ans);
    return 0;
}