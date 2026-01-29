#include "../include/fwd.h"

class Solution {
public:
    int minimumPairRemoval(vector<int>& nums) {
        int ans = 0;
        while (true) {
            // 先检查数组是否已经非递减
            bool is_non_decreasing = true;
            for (int i = 0; i < (int)nums.size() - 1; i++) {
                if (nums[i] > nums[i + 1]) {
                    is_non_decreasing = false;
                    break;
                }
            }
            if (is_non_decreasing) {
                return ans;
            }
            
            // 找所有相邻对中，和最小的一对
            int n = nums.size();
            int min_index = -1;
            int min_sum = INT_MAX;
            for (int i = 0; i < n - 1; i++) {
                int cur_sum = nums[i] + nums[i + 1];
                if (cur_sum < min_sum) {
                    min_sum = cur_sum;
                    min_index = i;
                }
            }
            
            // 执行替换和删除操作
            nums[min_index] = min_sum;
            for (int k = min_index + 1; k < n - 1; k++) {
                nums[k] = nums[k + 1];
            }
            nums.pop_back();
            ans++;
        }
        return ans;
    }
};

int main() {
    Solution solution;
    vector<int> nums = {1, 1, 4, 4, 2, -4, -1};
    cout << solution.minimumPairRemoval(nums) << endl;
    return 0;
}