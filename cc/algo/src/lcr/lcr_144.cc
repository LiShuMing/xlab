#include "../include/fwd.h"

class Solution {
public:
    TreeNode* flipTree(TreeNode* root) {
        if (!root) return nullptr;
        return dfs(root);
    }
    TreeNode* dfs(TreeNode* root) {
        if (!root) return nullptr;
        TreeNode* left = dfs(root->left);
        TreeNode* right = dfs(root->right);
        root->left = right;
        root->right = left;
        return root;
    }
};

int main() {
    Solution solution;
    TreeNode* root = new TreeNode(1, new TreeNode(2), new TreeNode(3));
    TreeNode* result = solution.flipTree(root);
    cout << result->val << endl;
    return 0;
}