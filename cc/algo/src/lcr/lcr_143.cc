#include "../include/fwd.h"

class Solution {
public:
    bool isSubStructure(TreeNode* root1, TreeNode* root2) {
        if (!root1 || !root2) return false;
        return dfs(root1, root2) || isSubStructure(root1->left, root2) || isSubStructure(root1->right, root2);
    }

    bool dfs(TreeNode* root1, TreeNode* root2) {
        if (!root2) return true;
        if (!root1) return false;
        if (root1->val != root2->val) return false;
        return dfs(root1->left, root2->left) && dfs(root1->right, root2->right);
    }
};

int main() {
    Solution solution;
    TreeNode* root1 = new TreeNode(1, new TreeNode(2), new TreeNode(3));
    TreeNode* root2 = new TreeNode(2, new TreeNode(3), new TreeNode(4));
    cout << solution.isSubStructure(root1, root2) << endl;
    return 0;
}