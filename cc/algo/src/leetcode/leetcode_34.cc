#include "../include/fwd.h"

class Solution {
public:
    vector<int> searchRange(vector<int>& nums, int target) {
        int n = nums.size();
        int left = 0;
        int right = n - 1;
        while (left <= right) {
            int mid = left + (right - left) / 2;
            if (nums[mid] == target) {
                int left = mid;
                int right = mid;
                while (left > 0 && nums[left - 1] == target) left--;
                while (right < n - 1 && nums[right + 1] == target) right++;
                return {left, right};
            }
            if (nums[mid] < target)
                left = mid + 1;
            else
                right = mid - 1;
        }
        return {-1, -1};
    }
};