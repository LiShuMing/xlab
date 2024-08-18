#include "../include/fwd.h"

class Solution {
public:
    int findTargetNode(TreeNode* root, int cnt) {
        if (root == NULL) {
            return -1;
        }
        int target = -1;
        traverse(root, cnt, target);
        return target;
    }
    void traverse(TreeNode* root, int& cnt, int& target) {
        if (root == NULL) {
            return;
        }
        traverse(root->right, cnt, target);
        if (cnt == 0) {
            return;
        }
        cnt--;
        if (cnt == 0) {
            target = root->val;
            return;
        }
        traverse(root->left, cnt, target);
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
    cout << solution.findTargetNode(root, 3) << endl;
    return 0;
}