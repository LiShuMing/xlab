#include "../include/fwd.h"

/**
713. 乘积小于 K 的子数组
给定一个整数数组 nums 和一个整数 k。

请你返回 子数组 内所有元素的 乘积严格小于 k 的连续子数组的数目。
 */
class Solution {
public:
    int numSubarrayProductLessThanK(vector<int>& nums, int k) {

        int l = 0, r = 0;
        long ans = 0;
        long p = 1;
        int n = nums.size();
        for (; r < n; r++) {
            p *= nums[r];
            while (l <= r && p >= k) {
                p /= nums[l++];
            }
            ans += (r - l + 1);
        }
        return ans;
    }
};
