#include "../include/fwd.h"

class Solution {
public:
    int minimumDifference(vector<int>& nums, int k) {
        int n = nums.size();
        int ans = INT_MAX;
        // for (int i = 0; i < n - k + 1; i++) {
        //     int min_val = INT_MAX;
        //     int max_val = INT_MIN;
        //     //
        //     for (int j = i; j < i + k; j++) {
        //         min_val = min(min_val, nums[j]);
        //         max_val = max(max_val, nums[j]);
        //     }
        //     ans = min(ans, max_val - min_val);
        // }

        sort(nums.begin(), nums.end());
        for (int i = 0; i < n - k + 1; i++) {
            ans = min(ans, nums[i + k - 1] - nums[i]);
        }
        return ans;
    }
};

int main() {
    Solution solution;
    vector<int> nums = {9, 4, 1, 7};
    int k = 2;
    cout << solution.minimumDifference(nums, k) << endl;
    return 0;
}