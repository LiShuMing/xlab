#include "../include/fwd.h"

/**
 * @brief 102. 二叉树的层序遍历
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

// class Solution {
// public:
//     vector<vector<int>> levelOrder(TreeNode* root) {
//         queue<TreeNode*> q;
//         if (root) {
//             q.push(root);
//         }
//         vector<vector<int>> result;
//         while (!q.empty()) {
//             int size = q.size();

//             vector<int> level;
//             for (int i = 0; i < size; i++) {
//                 TreeNode* node = q.front();
//                 q.pop();

//                 level.push_back(node->val);
//                 if (node->left) q.push(node->left);
//                 if (node->right) q.push(node->right);
//             }
//             result.push_back(level);
//         }
//         return result;
//     }
// };
class Solution {
public:
    vector<vector<int>> levelOrder(TreeNode* root) {
        vector<vector<int>> result;
        dfs(root, 0, result);
        return result;
    }

    void dfs(TreeNode* root, int level, vector<vector<int>>& result) {
        if (!root) {
            return;
        }
        if (level == result.size()) {
            result.push_back(vector<int>());
        }
        result[level].push_back(root->val);
        dfs(root->left, level + 1, result);
        dfs(root->right, level + 1, result);
    }
};
