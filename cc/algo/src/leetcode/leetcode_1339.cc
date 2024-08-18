#include "../include/fwd.h"
#include <climits>

class Solution {
private:
    static const long long MOD = 1000000007LL;
    long long _sum;
    long long _result;
    
    void dfs(TreeNode* root) {
        if (!root) return;
        _sum += root->val;
        dfs(root->left);
        dfs(root->right);
    }
    
    long long dfs2(TreeNode* root) {
        if (!root) return 0;
        long long cur = root->val + dfs2(root->left) + dfs2(root->right);
        long long product = (cur * (_sum - cur));
        if (product > _result) {
            _result = product;
        }
        return cur;
    }
    
public:
    Solution() : _sum(0), _result(LLONG_MIN) {}
    
    int maxProduct(TreeNode* root) {
        dfs(root);
        dfs2(root);
        return (int)(_result % MOD);
    }
};

int main() {
    Solution solution;
    TreeNode* root = new TreeNode(1, new TreeNode(2), new TreeNode(3));
    cout << solution.maxProduct(root) << endl;
    delete root;
    delete root->left;
    delete root->right;
    return 0;
}
