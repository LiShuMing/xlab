#include "../include/fwd.h"

class Solution {
public:
    bool isTrionic(vector<int>& nums) {
        int n = nums.size();
        if (nums[0] > nums[1]) {
            return false;
        }
        int cnt = 0;
        for (int i = 2; i < n - 1; i++) {
            if (nums[i] == nums[i - 1]) {
                return false;
            }
            if ((nums[i - 2] - nums[i - 1]) * (nums[i - 1] - nums[i]) < 0) {
                cnt++;
            }
            if (cnt > 3) {
                return false;
            }
        }
        return cnt == 3;
    }
};