#include "../include/fwd.h"

/**
给你一个整数数组 nums ，数组中的元素 互不相同 。返回该数组所有可能的子集（幂集）。
解集 不能 包含重复的子集。你可以按 任意顺序 返回解集。
 */

// class Solution {
// public:
//     vector<vector<int>> subsets(vector<int>& nums) {
//         int n = nums.size();
//         vector<vector<int>> result;

//         result.push_back({});
//         for (int i = 1; i <= n; i++) {
//             vector<int> path;
//             backtrack(nums, 0, i, path, result);
//         }
//         return result;
//     }

//     void backtrack(vector<int>& nums, int start, int size, vector<int>& path, vector<vector<int>>& result) {
//         if (start == size) {
//             result.push_back(path);
//             return;
//         }
//         for (int i = start; i < nums.size(); i++) {
//             path.push_back(nums[i]);
//             backtrack(nums, i + 1, size, path, result);
//             path.pop_back();
//         }
//     }
// };

class Solution {
public:
    vector<vector<int>> subsets(vector<int>& nums) {
        int n = nums.size();
        vector<vector<int>> result;
        vector<int> path;
        backtrack(nums, 0, path, result);
        return result;
    }

    void backtrack(vector<int>& nums, int i, vector<int>& path, vector<vector<int>>& result) {
        if (i == nums.size()) {
            result.push_back(path);
            return;
        }
        backtrack(nums, i + 1, path, result);
        path.push_back(nums[i]);
        backtrack(nums, i + 1, path, result);
        path.pop_back();
    }
};
