#include "../include/fwd.h"

class Solution {
public:
    vector<int> divingBoard(int shorter, int longer, int k) {
        if (k == 0) return {};
        if (shorter == longer) return {shorter * k};
        vector<int> ans;
        for (int i = 0; i <= k; i++) {
            ans.push_back(shorter * (k - i) + longer * i);
        }
        return ans;
    }
};

int main() {
    Solution solution;
    cout << solution.divingBoard(1, 2, 3) << endl;
    return 0;
}