#include "../include/fwd.h"

/**
 * 543. Diameter of Binary Tree
 * 
 * Given a binary tree, you need to compute the length of the diameter of the tree. 
 * The diameter of a binary tree is the length of the longest path between any two nodes in a tree. 
 * This path may or may not pass through the root.
 * 
 * Example:
 * Given a binary tree
 *           1
 *          / \
 *         2   3
 * The diameter of the tree is 3, which is the length of the path [4,2,1,3] or [5,2,1,3].
 */
 class Solution {
    public:
    int diameterOfBinaryTree(TreeNode* root) {
        return dfs(root, 0);
    }

    int dfs(TreeNode* node, int depth) {
        if (!node) {
            return depth;
        }
        int leftDepth = dfs(node->left, depth + 1);
        int rightDepth = dfs(node->right, depth + 1);
        return max(leftDepth, rightDepth);
    }
 };
 int main() {
    Solution solution;
    TreeNode* root = new TreeNode(1);
    root->left = new TreeNode(2);
    root->right = new TreeNode(3);
    root->left->left = new TreeNode(4);
    root->left->right = new TreeNode(5);
    cout << solution.diameterOfBinaryTree(root) << endl;
    return 0;
 }
