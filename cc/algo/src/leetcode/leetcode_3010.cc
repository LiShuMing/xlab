#include "../include/fwd.h"

class Solution {
public:
    int minimumCost(vector<int>& nums) {
        int n = nums.size();
        if (n < 3) {
            return 0;
        }
        int first = INT_MAX;
        int second = INT_MAX;
        for (int i = 1; i < n; i++) {
            int num = nums[i];
            if (num < first) {
                second = first;
                first = num;
            } else if (num < second) {
                second = num;
            }
        }
        return nums[0] + first + second;
    }
};