#include "../include/fwd.h"

class Solution {
public:
    int findMin(vector<int>& nums) {
        int n = nums.size();
        int left = 0;
        int right = n - 1;
        while (left < right) {
            int mid = left + (right - left) / 2;
            // right part is sorted
            if (nums[mid] < nums[right]) {
                right = mid;
            } else if (nums[mid] > nums[right]) {
                // left part is sorted
                left = mid + 1;
            } else {
                // nums[mid] == nums[right], cannot determine the side, safely shrink right
                right--;
            }
        }
        return nums[left];
    }
};