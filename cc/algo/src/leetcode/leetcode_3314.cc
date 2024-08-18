#include "../include/fwd.h"

class Solution {
public:
    vector<int> minBitwiseArray(vector<int>& nums) {
        int n = nums.size();
        vector<int> ans(n, 0);
        for (int i = 0; i < n; i++) {
            int x = nums[i];
            ans[i] =  x & 1 ? x ^ ((x + 1 & ~x) >> 1) : -1;
        }
        return ans;
    }
};

int main() {
    Solution solution;
    vector<int> nums = {1, 2, 3, 4, 5};
    cout << solution.minBitwiseArray(nums) << endl;
    return 0;
}