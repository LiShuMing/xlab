#include "../include/fwd.h"
class Solution {
public:
    int findMin(vector<int>& nums) {
        int n = nums.size();
        int l = 0, r = n - 1;
        while (l < r) {
            int mid = l + (r - l) / 2;
            if (nums[mid] < nums[r]) {
                r = mid;
            } else if (nums[mid] > nums[r]) {
                l = mid + 1;
            } else {
                // nums[mid] == nums[r], cannot determine the side, safely shrink r
                r--;
            }
        }
        return nums[l];
    }
};
int main() {
    Solution solution;
    int arr1[] = {4, 5, 6, 7, 0, 1, 2};
    vector<int> nums1(arr1, arr1 + sizeof(arr1) / sizeof(arr1[0]));
    cout << solution.findMin(nums1) << endl;

    int arr2[] = {2, 2, 2, 0, 1};
    vector<int> nums2(arr2, arr2 + sizeof(arr2) / sizeof(arr2[0]));
    cout << solution.findMin(nums2) << endl; // Should output 0 to test duplicates

    int arr3[] = {1, 1, 1, 1, 1};
    vector<int> nums3(arr3, arr3 + sizeof(arr3) / sizeof(arr3[0]));
    cout << solution.findMin(nums3) << endl; // All duplicates, should output 1

    return 0;
};