#include "../include/fwd.h"
class Solution {
public:
    long long minArraySum(vector<int>& nums, int k) {
        vector<long long> prefix_sum(k, LONG_MAX);
        prefix_sum[0] = 0;
        long long f = 0;
        int sum = 0;
        for (int i = 0; i < nums.size(); i++) {
            sum = (sum + nums[i]) % k;
            f = min(f + nums[i], prefix_sum[sum]);
            prefix_sum[sum] = f;
        }
        return f;
    }
};

int main() {
    Solution solution;
    vector<int> nums = {1, 2, 3, 4, 5};
    int k = 3;
    cout << solution.minArraySum(nums, k) << endl;
    return 0;
}