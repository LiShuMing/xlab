#include "../include/fwd.h"

class Node {
public:
    int val;
    Node* left;
    Node* right;

    Node() : val(0), left(nullptr), right(nullptr) {}

    Node(int _val) : val(_val), left(nullptr), right(nullptr) {}

    Node(int _val, Node* _left, Node* _right)
        : val(_val), left(_left), right(_right) {}
};  // Fixed missing semicolon here

class Solution {
public:
    Node* treeToDoublyList(Node* root) {
        if (!root) return nullptr;
        Node* prev = nullptr;
        Node* head = nullptr;
        dfs(root, prev, head);
        // make it circular
        if (head && prev) {
            head->left = prev;
            prev->right = head;
        }
        return head;
    }
    void dfs(Node* root, Node*& prev, Node*& head) {
        if (!root) return;
        // Traverse the left subtree
        dfs(root->left, prev, head);

        // If prev is nullptr, then root is the head of the list
        if (!prev) {
            head = root;
        } else {
            prev->right = root;
            root->left = prev;
        }
        prev = root;

        // Traverse the right subtree
        dfs(root->right, prev, head);
    }
};

int main() {
    Solution solution;
    Node* root = new Node(4, new Node(2, new Node(1), new Node(3)), new Node(5));
    Node* head = solution.treeToDoublyList(root);

    // Only print the circular list for one round to prevent infinite loop.
    if (head) {
        Node* curr = head;
        do {
            cout << curr->val << " ";
            curr = curr->right;
        } while (curr != head);
    }
    cout << endl;
    return 0;
}