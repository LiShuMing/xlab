#include "../include/fwd.h"

class Solution {
public:
    bool isValidBST(TreeNode* root) {
        return isValidBST(root, LLONG_MIN, LLONG_MAX);
    }
    bool isValidBST(TreeNode* root, long long min, long long max) {
        if (!root) return true;
        if (root->val <= min || root->val >= max) return false;
        return isValidBST(root->left, min, root->val) && isValidBST(root->right, root->val, max);
    }
};

int main() {
    Solution solution;
    TreeNode* root = new TreeNode(2, new TreeNode(1), new TreeNode(3));
    cout << solution.isValidBST(root) << endl;
    return 0;
}