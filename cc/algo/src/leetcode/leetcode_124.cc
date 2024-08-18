#include "../include/fwd.h"

class Solution {
private:
    int ans = INT_MIN;

public:
    int maxPathSum(TreeNode* root) {
        dfs(root);
        return ans;
    }
    int dfs(TreeNode* root) {
        if (!root) return 0;
        int left = max(0, dfs(root->left));
        int right = max(0, dfs(root->right));
        ans = max(ans, root->val + left + right);
        return root->val + max(left, right);
    }
};

int main() {
    Solution solution;
    TreeNode* root = new TreeNode(1, new TreeNode(2), new TreeNode(3));
    cout << solution.maxPathSum(root) << endl;
    return 0;
}