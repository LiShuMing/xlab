#include "../include/fwd.h"

class Solution {
public:
    int maxOperations(vector<int>& nums, int k) {
        int n = nums.size();
        int left = 0;
        int right = n - 1;
        int count = 0;
        sort(nums.begin(), nums.end());
        while (left < right) {
            int sum = nums[left] + nums[right];
            if (sum == k) {
                count++;
                left++;
                right--;
            } else if (sum < k) {
                left++;
            } else {
                right--;
            }
        }
        return count;
    }

    // use hash map
    int maxOperations2(vector<int>& nums, int k) {
        int n = nums.size();
        unordered_map<int, int> hm;
        int count = 0;
        for (auto i = 0; i < n; i++) {
            auto delta = k - nums[i];
            if (hm.find(delta) != hm.end() && hm[delta] > 0) {
                count++;
                hm[delta]--;
            } else {
                hm[nums[i]]++;
            }
        }
        return count;
    }
};
