#include "../include/fwd.h"

class Solution {
public:
    bool isValidBST(TreeNode* root) {
        if (!root) return true;
        if (root->left && root->left->val >= root->val) return false;
        if (root->right && root->right->val <= root->val) return false;
        return isValidBST(root->left) && isValidBST(root->right);
    }
};

int main() {
    Solution solution;
    TreeNode* root = new TreeNode(2, new TreeNode(1), new TreeNode(3));
    cout << solution.isValidBST(root) << endl;
    return 0;
}