#include "../include/fwd.h"
class Solution {
public:
    int maximumGap(vector<int>& nums) {
        // use bucket sort to sort the numbers
        int n = nums.size();
        if (n < 2) return 0;
        int max_num = *max_element(nums.begin(), nums.end());
        int min_num = *min_element(nums.begin(), nums.end());
        int d = max(1, (max_num - min_num) / (n - 1));
        int bucket_count = (max_num - min_num) / d + 1;
        vector<pair<int, int>> buckets(bucket_count, make_pair(-1, -1));
        for (int i = 0; i < n; i++) {
            int index = (nums[i] - min_num) / d;
            if (buckets[index].first == -1) {
                buckets[index].first = nums[i];
                buckets[index].second = nums[i];
            } else {
                buckets[index].first = min(buckets[index].first, nums[i]);
                buckets[index].second = max(buckets[index].second, nums[i]);
            }
        }
        int max_gap = 0;
        int prev = -1;
        for (int i = 0; i < bucket_count; i++) {
            if (buckets[i].first == -1) {
                continue;
            }
            if (prev != -1) {
                max_gap = max(max_gap, buckets[i].first - buckets[prev].second);
            }
            prev = i;
        }
        return max_gap;
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