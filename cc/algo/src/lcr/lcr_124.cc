#include "../include/fwd.h"
class Solution {
public:
    TreeNode* deduceTree(vector<int>& preorder, vector<int>& inorder) {
        if (preorder.empty() || inorder.empty()) return nullptr;
        return buildTree(preorder, 0, preorder.size() - 1, inorder, 0, inorder.size() - 1);
    }

    TreeNode* buildTree(const vector<int>& preorder, int preStart, int preEnd,
                        const vector<int>& inorder, int inStart, int inEnd) {
        if (preStart > preEnd || inStart > inEnd) return nullptr;
        TreeNode* root = new TreeNode(preorder[preStart]);
        int rootIndex = std::find(inorder.begin() + inStart, inorder.end() + inEnd, root->val) -
                        inorder.begin();
        root->left = buildTree(preorder, preStart + 1, preStart + rootIndex - inStart, inorder,
                               inStart, rootIndex - 1);
        root->right = buildTree(preorder, preStart + rootIndex - inStart + 1, preEnd, inorder,
                                rootIndex + 1, inEnd);
        return root;
    }
};
int main() {
    Solution solution;
    vector<int> preorder = {3, 9, 20, 15, 7};
    vector<int> inorder = {9, 3, 15, 20, 7};
    TreeNode* root = solution.deduceTree(preorder, inorder);
    cout << root->val << endl;
    return 0;
}