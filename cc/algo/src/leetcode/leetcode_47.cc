#include "../include/fwd.h"

class Solution {
public:
    vector<vector<int>> subsets(vector<int>& nums) {
        vector<vector<int>> result;
        for (int i = 0; i <= nums.size(); i++) {
            vector<int> subset;
            backtrack(nums, 0, i, subset, result);
        }
        return result;
    }

    void backtrack(vector<int>& nums, int start, int k, vector<int>& subset, vector<vector<int>>& result) {
        if (subset.size() == k) {
            result.push_back(subset);
            return;
        }
        for (int i = start; i < nums.size(); i++) {
            subset.push_back(nums[i]);
            backtrack(nums, i + 1, k, subset, result);
            subset.pop_back();
        }
    }
};

int main() {
    Solution solution;
    vector<int> nums = {1, 2, 3};
    vector<vector<int>> result = solution.subsets(nums);
    for (auto& subset : result) {
        for (auto& num : subset) {
            cout << num << " ";
        }
        cout << endl;
    }
    return 0;
}