#include "../include/fwd.h"
class Solution {
public:
    TreeNode* buildTree(vector<int>& inorder, vector<int>& postorder) {
        if (inorder.empty() || postorder.empty()) return nullptr;
        return buildTreeHelper(inorder, 0, inorder.size() - 1, postorder, 0, postorder.size() - 1);
    }
    TreeNode* buildTreeHelper(vector<int>& inorder, int inStart, int inEnd, vector<int>& postorder, int postStart, int postEnd) {
        if (inStart > inEnd || postStart > postEnd) return nullptr;
        TreeNode* root = new TreeNode(postorder[postEnd]);
        int rootIndex = std::find(inorder.begin() + inStart, inorder.end() + inEnd, root->val) - inorder.begin();
        root->left = buildTreeHelper(inorder, inStart, rootIndex - 1, postorder, postStart, postStart + rootIndex - inStart - 1);
        root->right = buildTreeHelper(inorder, rootIndex + 1, inEnd, postorder, postStart + rootIndex - inStart, postEnd - 1);
        return root;
    }
};