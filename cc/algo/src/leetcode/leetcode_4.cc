#include "../include/fwd.h"
#include <climits>

class Solution {
public:
    /**
     * Find the median of two sorted arrays
     * 
     * Algorithm: Binary Search on Partition
     * 
     * Key Idea:
     * - We partition both arrays such that:
     *   left partition: A[0..mid-1] + B[0..j-1]  (total = (m+n+1)/2 elements)
     *   right partition: A[mid..] + B[j..]      (remaining elements)
     * - The median is found when:
     *   maxLeft1 <= minRight2 AND maxLeft2 <= minRight1
     * 
     * Time Complexity: O(log(min(m, n)))
     * Space Complexity: O(1)
     */
    double findMedianSortedArrays(vector<int>& nums1, vector<int>& nums2) {
        // Ensure nums1 is the smaller array for efficiency
        if (nums1.size() > nums2.size()) {
            return findMedianSortedArrays(nums2, nums1);
        }
        
        int m = nums1.size();
        int n = nums2.size();
        
        // Binary search on nums1
        // We search for partition point 'mid' in nums1
        // such that: left side has (m+n+1)/2 elements total
        int left = 0;
        int right = m;  // mid can be from 0 to m (inclusive of m means empty right part)
        
        while (left <= right) {
            // mid: number of elements from nums1 in left partition
            int mid = left + (right - left) / 2;
            
            // j: number of elements from nums2 in left partition
            // We want left partition to have (m+n+1)/2 elements total
            int j = (m + n + 1) / 2 - mid;
            
            // Edge cases for boundaries:
            // If mid == 0: left partition has no elements from nums1
            // If mid == m: right partition has no elements from nums1
            // Same for j with nums2
            
            int maxLeft1 = (mid == 0) ? INT_MIN : nums1[mid - 1];
            int maxLeft2 = (j == 0) ? INT_MIN : nums2[j - 1];
            int minRight1 = (mid == m) ? INT_MAX : nums1[mid];
            int minRight2 = (j == n) ? INT_MAX : nums2[j];
            
            // Check if we found the correct partition
            // Condition: all elements in left <= all elements in right
            if (maxLeft1 <= minRight2 && maxLeft2 <= minRight1) {
                // Found the median partition!
                if ((m + n) % 2 == 0) {
                    // Even total: average of two middle values
                    // (maxLeft1, maxLeft2) are the two largest in left partition
                    // (minRight1, minRight2) are the two smallest in right partition
                    double left_max = max(maxLeft1, maxLeft2);
                    double right_min = min(minRight1, minRight2);
                    return (left_max + right_min) / 2.0;
                } else {
                    // Odd total: median is the middle value (largest in left partition)
                    return static_cast<double>(max(maxLeft1, maxLeft2));
                }
            } 
            // If maxLeft1 > minRight2, mid is too large, move left
            else if (maxLeft1 > minRight2) {
                right = mid - 1;
            } 
            // If maxLeft2 > minRight1, mid is too small, move right
            else {
                left = mid + 1;
            }
        }
        
        // Should not reach here if inputs are valid
        return 0.0;
    }
};

int main() {
    Solution solution;
    
    // Test case 1: nums1 = {1, 3}, nums2 = {2}
    // Expected: 2.0 (median of {1, 2, 3})
    int arr1[] = {1, 3};
    int arr2[] = {2};
    vector<int> nums1(arr1, arr1 + 2);
    vector<int> nums2(arr2, arr2 + 1);
    cout << "Test 1: " << solution.findMedianSortedArrays(nums1, nums2) << endl;
    
    // Test case 2: nums1 = {1, 2}, nums2 = {3, 4}
    // Expected: 2.5 (median of {1, 2, 3, 4})
    int arr3[] = {1, 2};
    int arr4[] = {3, 4};
    vector<int> nums3(arr3, arr3 + 2);
    vector<int> nums4(arr4, arr4 + 2);
    cout << "Test 2: " << solution.findMedianSortedArrays(nums3, nums4) << endl;
    
    return 0;
}
