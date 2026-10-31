#include "../include/fwd.h"
// class Solution {
// public:
//     void backtrack(vector<int>& nums, int start, vector<vector<int>>& result) {
//         if (start == nums.size()) {
//             result.push_back(nums);
//             return;
//         }
//         for (int i = start; i < nums.size(); i++) {
//             swap(nums[start], nums[i]);
//             backtrack(nums, start + 1, result);
//             swap(nums[start], nums[i]);
//         }
//     }
//     vector<vector<int>> permute(vector<int>& nums) {
//         vector<vector<int>> result;
//         backtrack(nums, 0, result);
//         return result;
//     }
// };

class Solution {
public:
    vector<vector<int>> permute(vector<int>& nums) {
        vector<vector<int>> ans;
        vector<int> path;
        vector<bool> used(nums.size(), false);  // used[i]：nums[i] 是否已经被放进 path
        dfs(nums, used, path, ans);
        return ans;
    }

    // path: 已经排好的前缀，长度就是「这一位该填第几个」
    void dfs(vector<int>& nums, vector<bool>& used, vector<int>& path, vector<vector<int>>& ans) {
        if (path.size() == nums.size()) {  // 所有元素都用上了，得到一条完整排列
            ans.emplace_back(path);
            return;
        }
        // 每层从「剩下没用过的元素」里挑一个，放到当前这一位
        for (size_t i = 0; i < nums.size(); i++) {
            if (used[i]) continue;        // 已经被前面的位用过，跳过
            used[i] = true;               // 1. 选中 nums[i]
            path.emplace_back(nums[i]);   // 2. 放进路径
            dfs(nums, used, path, ans);   // 3. 递归排剩下的位置
            path.pop_back();              // 4. 回溯：撤销路径
            used[i] = false;              // 5. 回溯：撤销标记
        }
    }
};

int main() {
    Solution solution;
    vector<int> nums = {1, 2, 3};
    vector<vector<int>> result = solution.permute(nums);

    cout << "result (" << result.size() << " 条):" << endl;
    for (const auto& vec : result) {
        cout << "[" << strJoin(vec, " ") << "]" << endl;  // 每条排列单独一行，行内无多余空格
    }
    return 0;
}
