#include "../include/fwd.h"

/**
 * LeetCode 173: Binary Search Tree Iterator
 * 
 * Implement an iterator over a binary search tree (BST) that:
 * - next(): returns the next smallest element in the BST
 * - hasNext(): returns true if there are more elements to iterate
 * 
 * Average time complexity: O(1) amortized per operation
 * Average space complexity: O(h) where h is tree height
 */
class BSTIterator {
private:
    stack<TreeNode*> st;
    
    // Helper function: push all left nodes onto stack
    void pushAll(TreeNode* node) {
        while (node) {
            st.push(node);
            node = node->left;
        }
    }
    
public:
    /**
     * Constructor: Initialize the iterator with the smallest element
     * by pushing all left nodes from the root onto the stack.
     */
    BSTIterator(TreeNode* root) {
        pushAll(root);
    }
    
    /**
     * next(): Returns the next smallest element in the BST.
     * Steps:
     * 1. Pop the top node (smallest element)
     * 2. Push all left nodes from its right subtree
     * 3. Return the node's value
     */
    int next() {
        TreeNode* node = st.top();
        st.pop();
        pushAll(node->right);
        return node->val;
    }
    
    /**
     * hasNext(): Returns true if there are more elements to iterate.
     */
    bool hasNext() {
        return !st.empty();
    }
};
