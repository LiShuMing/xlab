#include "../include/fwd.h"

class Solution {
public:
    bool isBalanced(TreeNode* root) {
        if (root == NULL) {
            return true;
        }
        return isBalanced(root->left) && isBalanced(root->right) &&
               abs(calculateDepth(root->left) - calculateDepth(root->right)) <= 1;
    }
    int calculateDepth(TreeNode* root) {
        if (root == NULL) {
            return 0;
        }
        return 1 + max(calculateDepth(root->left), calculateDepth(root->right));
    }
};
int main() {
    Solution solution;
    TreeNode* root = new TreeNode(1);
    root->left = new TreeNode(2);
    root->right = new TreeNode(3);
    root->left->left = new TreeNode(4);
    root->left->right = new TreeNode(5);
    root->right->left = new TreeNode(6);
    root->right->right = new TreeNode(7);
    cout << solution.isBalanced(root) << endl;
    return 0;
}