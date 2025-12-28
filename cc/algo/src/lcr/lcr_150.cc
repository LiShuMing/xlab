#include "../include/fwd.h"
class Solution {
public:
    vector<vector<int>> decorateRecord(TreeNode* root) {
        if (!root) return {};
        vector<vector<int>> ans;
        queue<pair<TreeNode*, int>> q;
        int level = 0;
        q.push({root, level});
        while (!q.empty()) {
            TreeNode* node = q.front().first;
            int level = q.front().second;
            q.pop();
            if (!node) continue;
            if (level == ans.size()) {
                ans.push_back(vector<int>());
            }
            ans[level].push_back(node->val);
            if (node->left) q.push({node->left, level + 1});
            if (node->right) q.push({node->right, level + 1});
        }
        return ans;
    }
};

int main() {
    Solution solution;
    TreeNode* root = new TreeNode(1, new TreeNode(2), new TreeNode(3));
    vector<vector<int>> ans = solution.decorateRecord(root);
    for (int i = 0; i < ans.size(); i++) {
        for (int j = 0; j < ans[i].size(); j++) {
            cout << ans[i][j] << " ";
        }
        cout << endl;
    }
    return 0;
}