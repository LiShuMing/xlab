#include "../include/fwd.h"

/**
 * 783. Minimum Distance Between BST Nodes
 * 
 * Given the root of a Binary Search Tree (BST), return the minimum difference between the values of any two different nodes in the tree.
 * 
 * Example:
 * Input: root = [4,2,6,1,3]
 * Output: 1
 * 
 * Constraints:
 * The number of nodes in the tree is in the range [2, 100].
 * 0 <= Node.val <= 10^5
 */
 class Solution {
    public:
        int minDiffInBST(TreeNode* root) {
            int minDiff = INT_MAX;
            int prev = -1;
            inorderTraversal(root, minDiff, prev);
            return minDiff;
        }
        void inorderTraversal(TreeNode* root, int& minDiff, int& prev) {
            if (!root) return;
            inorderTraversal(root->left, minDiff, prev);
            if (prev != -1) {
                minDiff = min(minDiff, root->val - prev);
            }
            prev = root->val;
            inorderTraversal(root->right, minDiff, prev);
        }
    };