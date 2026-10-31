#include "../include/fwd.h"

// class Solution {
// public:
//     int search(vector<int>& nums, int target) {
//         int n = nums.size();
//         int left = 0;
//         int right = n - 1;
//         while (left <= right) {
//             int mid = left + (right - left) / 2;
//             if (nums[mid] == target) return mid;
//             if (nums[mid] < nums[right]) {
//                 // right part is sorted
//                 if (target > nums[mid] && target <= nums[right])
//                     left = mid + 1;
//                 else
//                     right = mid - 1;
//             } else {
//                 // left part is sorted
//                 if (target < nums[mid] && target >= nums[left])
//                     right = mid - 1;
//                 else
//                     left = mid + 1;
//             }
//         }
//         return -1;
//     }
// };

// 4,5,6,7,0,1,2

// 4,5,6,7,0,1,2
class Solution {
public:
    int search(vector<int>& nums, int target) {
        int n = nums.size();
        int l = 0;
        int r = n - 1;
        while (l <= r) {
            int mid = l + (r - l) / 2;
            if (nums[mid] == target) return mid;

            // 只有在 right part is sorted 的情况下，才有可能在 right part 找到 target
            if (nums[mid] < nums[r]) {
                // right part is sorted
                if (target > nums[mid] && target <= nums[r])
                    l = mid + 1;
                else
                    r = mid - 1;
            } else {
                // 只有在 left part is sorted 的情况下，才有可能在 left part 找到 target
                // left part is sorted
                if (target < nums[mid] && target >= nums[l])
                    r = mid - 1;
                else
                    l = mid + 1;
            }
        }
        return -1;
    }
};
