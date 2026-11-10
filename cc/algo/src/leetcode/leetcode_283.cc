#include "../include/fwd.h"

class Solution {
public:
    void moveZeroes(vector<int>& nums) {
        int n = nums.size();
        int l = 0;
        int r = 0;
        while (r < n) {
            if (nums[r] != 0) {
                if (l != r) {
                    swap(nums[l], nums[r]);
                }
                l++;
            }
            r++;
        }
    }
};
