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
 *        /
 *       4
 * The diameter of the tree is 3, which is the path [4,2,1,3] (4 edges: 4->2->1->3)
 */
class Solution {
private:
    int maxDiameter;

    int dfs(TreeNode* node) {
        if (!node) {
            return 0;
        }
        int leftDepth = dfs(node->left);
        int rightDepth = dfs(node->right);
        // Update the maximum diameter (path through this node)
        maxDiameter = max(maxDiameter, leftDepth + rightDepth);
        // Return the depth of this subtree
        return max(leftDepth, rightDepth) + 1;
    }

public:
    int diameterOfBinaryTree(TreeNode* root) {
        maxDiameter = 0;
        dfs(root);
        return maxDiameter;
    }
};

int main() {
    Solution solution;
    // Build tree:       1
    //                  / \
    //                 2   3
    //                /
    //               4
    // Diameter: path 4->2->1->3 = 3 edges
    TreeNode* root = new TreeNode(1);
    root->left = new TreeNode(2);
    root->right = new TreeNode(3);
    root->left->left = new TreeNode(4);

    int result = solution.diameterOfBinaryTree(root);
    cout << "Diameter: " << result << endl;  // Expected: 3 (path 4-2-1-3)

    // Cleanup
    delete root->left->left;
    delete root->left;
    delete root->right;
    delete root;

    return 0;
}
