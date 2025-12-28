#include "../include/fwd.h"

class Solution {
public:
    // recursive inorder traversal
    vector<int> inorderTraversal(TreeNode* root) {
        vector<int> ans;
        inorderTraversal(root, ans);
        return ans;
    }
    void inorderTraversal(TreeNode* root, vector<int>& ans) {
        if (!root) return;
        inorderTraversal(root->left, ans);
        ans.push_back(root->val);
        inorderTraversal(root->right, ans);
    }

    // iterative inorder traversal
    vector<int> inorderTraversalIterative(TreeNode* root) {
        vector<int> ans;
        stack<TreeNode*> st;
        while (root || !st.empty()) {
            while (root) {
                st.push(root);
                root = root->left;
            }
            root = st.top();
            st.pop();
            ans.push_back(root->val);
            root = root->right;
        }
        return ans;
    }

    // recursive preorder traversal
    vector<int> preorderTraversal(TreeNode* root) {
        vector<int> ans;
        preorderTraversal(root, ans);
        return ans;
    }
    void preorderTraversal(TreeNode* root, vector<int>& ans) {
        if (!root) return;
        ans.push_back(root->val);
        preorderTraversal(root->left, ans);
        preorderTraversal(root->right, ans);
    }

    // iterative preorder traversal
    vector<int> preorderTraversalIterative(TreeNode* root) {
        vector<int> ans;
        stack<TreeNode*> st;
        while (root || !st.empty()) {
            while (root) {
                ans.push_back(root->val);
                st.push(root);
                root = root->left;
            }
            root = st.top();
            st.pop();
            root = root->right;
        }
        return ans;
    }

    // recursive postorder traversal
    vector<int> postorderTraversal(TreeNode* root) {
        vector<int> ans;
        postorderTraversal(root, ans);
        return ans;
    }
    void postorderTraversal(TreeNode* root, vector<int>& ans) {
        if (!root) return;
        postorderTraversal(root->left, ans);
        postorderTraversal(root->right, ans);
        ans.push_back(root->val);
    }

    // iterative postorder traversal
    vector<int> postorderTraversalIterative(TreeNode* root) {
        vector<int> ans;
        if (!root) return ans;
        
        stack<TreeNode*> st;
        TreeNode* lastVisited = nullptr;
        
        while (root || !st.empty()) {
            // Go to the leftmost node
            while (root) {
                st.push(root);
                root = root->left;
            }
            
            TreeNode* node = st.top();
            // If right child exists and hasn't been processed yet
            if (node->right && node->right != lastVisited) {
                root = node->right;
            } else {
                // Process the node
                ans.push_back(node->val);
                lastVisited = node;
                st.pop();
            }
        }
        return ans;
    }
};

int main() {
    Solution solution;
    TreeNode* root = new TreeNode(1, new TreeNode(2, new TreeNode(4), new TreeNode(5)), new TreeNode(3, new TreeNode(6), new TreeNode(7)));
    vector<int> ans = solution.inorderTraversal(root);
    cout << "inorderTraversal: ";
    printVector(ans);
    ans = solution.inorderTraversalIterative(root);
    cout << "inorderTraversalIterative: ";
    printVector(ans);

    ans = solution.preorderTraversal(root);
    cout << "preorderTraversal: ";
    printVector(ans);
    ans = solution.preorderTraversalIterative(root);
    cout << "preorderTraversalIterative: ";
    printVector(ans);

    ans = solution.postorderTraversal(root);
    cout << "postorderTraversal: ";
    printVector(ans);
    ans = solution.postorderTraversalIterative(root);
    cout << "postorderTraversalIterative: ";
    printVector(ans);
    return 0;
}