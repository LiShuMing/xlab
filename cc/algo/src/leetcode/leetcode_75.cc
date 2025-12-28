#include "../include/fwd.h"

class Solution {
public:
    void sortColors(vector<int>& nums) {
        int n = nums.size();
        int l = 0, r = n - 1;
        int i = 0;
        while (i <= r) {
            if (nums[i] == 0) {
                swap(nums[i], nums[l]);
                l++;
            }
            i++;
        }
        // After first pass, all 0s are at positions [0, l-1]
        // Now process the remaining part [l, r] to separate 1s and 2s
        i = l;
        while (i <= r) {
            if (nums[i] == 1) {
                i++;
            } else if (nums[i] == 2) {
                swap(nums[i], nums[r]);
                r--;
                // Don't increment i here, need to check the swapped value
            } else {
                // This shouldn't happen after first pass, but handle it
                i++;
            }
        }
    }
};

int main() {
    Solution solution;
    vector<vector<int>> test_cases = {
        {2, 0, 2, 1, 1, 0},
        {2, 0, 1},
        {0},
        {1},
        {2},
        {1, 2, 0}
    };
    
    for (auto& nums : test_cases) {
        vector<int> original = nums;
        solution.sortColors(nums);
        cout << "Input: ";
        for (int num : original) cout << num << " ";
        cout << "-> Output: ";
        for (int num : nums) cout << num << " ";
        cout << endl;
    }
    return 0;
}