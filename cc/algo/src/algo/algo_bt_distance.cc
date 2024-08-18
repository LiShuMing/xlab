#include "../include/fwd.h"

class Solution {
public:
    int distance(TreeNode* root, TreeNode* p, TreeNode* q) {
        if (!root) return 0;
        // find the lowest common ancestor of p and q
        TreeNode* lca = lowestCommonAncestor(root, p, q);
        // calculate the distance from the lca to p and q
        return distanceFromRoot(lca, p) + distanceFromRoot(lca, q);
    }
    TreeNode* lowestCommonAncestor(TreeNode* root, TreeNode* p, TreeNode* q) {
        if (!root) return nullptr;
        if (root == p || root == q) return root;
        TreeNode* left = lowestCommonAncestor(root->left, p, q);
        TreeNode* right = lowestCommonAncestor(root->right, p, q);
        if (left && right) return root;
        return left ? left : right;
    }
    int distanceFromRoot(TreeNode* root, TreeNode* node) {
        if (!root) return 0;
        if (root == node) return 0;
        return 1 + distanceFromRoot(root->left, node) + distanceFromRoot(root->right, node);
    }
};

int main() {
    Solution solution;
    return 0;
}