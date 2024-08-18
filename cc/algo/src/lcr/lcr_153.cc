#include "../include/fwd.h"

class Solution {
public:
    vector<vector<int>> pathTarget(TreeNode* root, int target) {
        vector<vector<int>> paths;
        vector<int> path;
        dfs(root, target, 0, path, paths);
        return paths;
    }
    void dfs(TreeNode* root, int target, int sum, vector<int>& path, vector<vector<int>>& paths) {
        if (!root) return;

        sum += root->val;
        path.push_back(root->val);
        // Only add to paths if it's a leaf and the sum matches the target
        if (!root->left && !root->right && sum == target) {
            paths.push_back(path);
        } else {
            dfs(root->left, target, sum, path, paths);
            dfs(root->right, target, sum, path, paths);
        }
        path.pop_back();
        // No need to subtract from sum, as sum is passed by value
    }
};

int main() {
    Solution solution;
    TreeNode* root = new TreeNode(1, new TreeNode(2, new TreeNode(4), new TreeNode(5)), new TreeNode(3, new TreeNode(6), new TreeNode(7)));
    vector<vector<int>> paths = solution.pathTarget(root, 3);
    for (auto& path : paths) {
        for (auto& val : path) {
            cout << val << " ";
        }
        cout << endl;
    }
    return 0;
}