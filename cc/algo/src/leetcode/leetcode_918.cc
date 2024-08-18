#include <climits>
#include <numeric>

#include "../include/fwd.h"

class Solution {
public:
    int maxSubarraySumCircular(vector<int>& nums) {
        int n = nums.size();

        vector<int> left_max(n, 0);
        int left_sum = nums[0];
        left_max[0] = nums[0];
        int max_sum = nums[0];
        int current_sum = nums[0];
        for (int i = 1; i < n; i++) {
            current_sum = max(current_sum + nums[i], nums[i]);
            max_sum = max(max_sum, current_sum);

            left_sum += nums[i];
            left_max[i] = max(left_max[i - 1], left_sum);
        }

        int right_sum = 0;
        for (int i = n - 1; i > 0; i--) {
            right_sum += nums[i];
            max_sum = max(max_sum, right_sum + left_max[i - 1]);
        }
        return max_sum;
    }
};
int main() {
    Solution solution;
    vector<int> nums = {5, -3, 5};
    cout << solution.maxSubarraySumCircular(nums) << endl;
    return 0;
}