#include "../include/fwd.h"

class Solution {
public:
    int maxLevelSum(TreeNode* root) {
        if (!root) return 0;
        queue<TreeNode*> q;
        q.push(root);
        int max_sum = INT_MIN;
        int max_level = 1;
        int level = 0;
        while (!q.empty()) {
            int size = q.size();
            int sum = 0;
            for (int i = 0; i < size; i++) {
                TreeNode* node = q.front();
                q.pop();
                sum += node->val;
                if (node->left) q.push(node->left);
                if (node->right) q.push(node->right);
            }
            if (sum > max_sum) {
                max_sum = sum;
                max_level = level;
            }
            level++;
        }
        return max_level;
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
    cout << solution.maxLevelSum(root) << endl;
    delete root;
    delete root->left;
    delete root->right;
    delete root->left->left;
    delete root->left->right;
    delete root->right->left;
    delete root->right->right;
    return 0;
}