#include "../include/fwd.h"
class Solution {
public:
    int max_depth = 0;
    TreeNode* subtreeWithAllDeepest(TreeNode* root) {
        max_depth = 0;
        // get the max depth of the tree
        dfs(root, 0);
        // find the subtree with all deepest nodes
        return dfs2(root, 0);
    }
    TreeNode* dfs2(TreeNode* root, int depth) {
        if (!root) return nullptr;
        if (depth == max_depth) {
            return root;
        }
        TreeNode* left = dfs2(root->left, depth + 1);
        TreeNode* right = dfs2(root->right, depth + 1);
        if (left && right) {
            return root;
        }
        return left ? left : right;
    }
    void dfs(TreeNode* root, int depth) {
        if (!root) return;
        if (depth > max_depth) {
            max_depth = depth;
        }
        dfs(root->left, depth + 1);
        dfs(root->right, depth + 1);
    }
};