#include "../include/fwd.h"

class Solution {
public:
    int kthSmallest(TreeNode* root, int k) {
        if (!root) return -1;
        stack<TreeNode*> st;
        while (root || !st.empty()) {
            while (root) {
                st.push(root);
                root = root->left;
            }
            root = st.top();
            st.pop();
            if (--k == 0) return root->val;
            root = root->right;
        }
        return -1;
    }
};
int main() {
    Solution solution;
    TreeNode* root = new TreeNode(3);
    root->left = new TreeNode(1);
    root->right = new TreeNode(4);
    root->left->right = new TreeNode(2);
    cout << solution.kthSmallest(root, 2) << endl;
    return 0;
}