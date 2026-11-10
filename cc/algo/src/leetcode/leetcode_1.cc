#include "../include/fwd.h"

class Solution {
public:
    vector<int> twoSum(vector<int>& nums, int target) {
        unordered_map<int, int> hm;
        size_t n = nums.size();
        for (auto i = 0; i < n; i++) {
            auto delta = target - nums[i];
            if (hm.find(delta) == hm.end()) {
                hm.emplace(nums[i], i);
            } else {
                return {i, hm[delta]};
            }
        }
        return {};
    }
};
