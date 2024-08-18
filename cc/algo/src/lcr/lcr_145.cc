#include "../include/fwd.h"
class Solution {
public:
    bool checkSymmetricTree(TreeNode* root) {
        if (!root) return true;
        return dfs(root->left, root->right);
    }
    bool dfs(TreeNode* left, TreeNode* right) {
        if (!left && !right) return true;
        if (!left || !right) return false;
        if (left->val != right->val) return false;
        return dfs(left->left, right->right) && dfs(left->right, right->left);
    }
};

int main() {
    Solution solution;
    TreeNode* root = new TreeNode(1, new TreeNode(2), new TreeNode(2));
    cout << solution.checkSymmetricTree(root) << endl;
    return 0;
}