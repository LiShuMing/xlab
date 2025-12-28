#include "../include/fwd.h"

/**
 * Definition for a binary tree node.
 * struct TreeNode {
 *     int val;
 *     TreeNode *left;
 *     TreeNode *right;
 *     TreeNode() : val(0), left(nullptr), right(nullptr) {}
 *     TreeNode(int x) : val(x), left(nullptr), right(nullptr) {}
 *     TreeNode(int x, TreeNode *left, TreeNode *right) : val(x), left(left), right(right) {}
 * };
 */
class Solution {
public:
    int pathSum(TreeNode* root, int targetSum) {
        if (!root) return 0;
        return countFrom(root, targetSum) + pathSum(root->left, targetSum) + pathSum(root->right, targetSum);
    }

    int countFrom(TreeNode* node, long long sum) {
        if (!node) return 0;
        int count = (node->val == sum ? 1 : 0);
        count += countFrom(node->left, sum - node->val);
        count += countFrom(node->right, sum - node->val);
        return count;
    }
};

int main() {
    Solution solution;
    TreeNode* root = new TreeNode(1, new TreeNode(2), new TreeNode(3));
    cout << solution.pathSum(root, 3) << endl;
    return 0;
}