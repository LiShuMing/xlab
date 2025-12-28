#include "../include/fwd.h"

class Solution {
public:
    TreeNode* lowestCommonAncestor(TreeNode* root, TreeNode* p, TreeNode* q) {
        if (!root) return nullptr;
        if (root->val > p->val && root->val > q->val) {
            return lowestCommonAncestor(root->left, p, q);
        }
        if (root->val < p->val && root->val < q->val) {
            return lowestCommonAncestor(root->right, p, q);
        }
        return root;
    }
};

int main() {
    Solution solution;
    TreeNode* root = new TreeNode(
            6, new TreeNode(2, new TreeNode(0), new TreeNode(4, new TreeNode(3), new TreeNode(5))),
            new TreeNode(8, new TreeNode(7), new TreeNode(9)));
    TreeNode* p = root->left->right;
    TreeNode* q = root->right->left;
    TreeNode* ans = solution.lowestCommonAncestor(root, p, q);
    cout << ans->val << endl;
    return 0;
}