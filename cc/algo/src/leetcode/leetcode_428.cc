#include "../include/fwd.h"

/**
Serialization is the process of converting a data structure or object into a sequence of bits so that it can be stored in a file or memory buffer, or transmitted across a network connection link to be reconstructed later in the same or another computer environment.

Design an algorithm to serialize and deserialize an N-ary tree. An N-ary tree is a rooted tree in which each node has no more than N children. There is no restriction on how your serialization/deserialization algorithm should work. You just need to ensure that an N-ary tree can be serialized to a string and this string can be deserialized to the original tree structure.

For example, you may serialize the following 3-ary tree:

            1
          / | \
         3  2  4
        / \
       5   6

as [1 [3[5 6] 2 4]]. You do not necessarily need to follow this format, so please be creative and come up with different approaches yourself.

Note:
1. The number of nodes in the tree is between 0 and 10,000.
2. The number of children of each node is between 0 and 10,000.
3. Do not use class member/global/static variables to store states. Your serialize and deserialize algorithms should be stateless.
 */
class Solution {
public:
    string serialize(NaryTreeNode* root) {
        if (!root) return "";
        string ans;
        queue<NaryTreeNode*> q;
        q.push(root);
        while (!q.empty()) {
            NaryTreeNode* node = q.front();
            q.pop();
            if (node) {
                ans += to_string(node->val) + ",";

                ans += to_string(node->children.size()) + ",";
                for (auto child : node->children) {
                    q.push(child);
                }
            }
        }
        return ans;
    }
    
    NaryTreeNode* deserialize(string data) {
        if (data.empty()) return nullptr;
        vector<string> tokens = split(data, ",");
        if (tokens.empty()) return nullptr;
        
        int idx = 0;
        if (idx + 1 >= tokens.size()) return nullptr;
        
        // Read root: value and children count
        int rootVal = stoi(tokens[idx++]);
        int rootNumChildren = stoi(tokens[idx++]);
        NaryTreeNode* root = new NaryTreeNode(rootVal);
        
        // Use queue to store (node, numChildren) pairs
        queue<pair<NaryTreeNode*, int> > q;
        q.push(make_pair(root, rootNumChildren));
        
        while (!q.empty() && idx < tokens.size()) {
            NaryTreeNode* node = q.front().first;
            int numChildren = q.front().second;
            q.pop();
            
            // Read all children for this node
            for (int i = 0; i < numChildren; i++) {
                if (idx + 1 >= tokens.size()) break;
                int childVal = stoi(tokens[idx++]);
                int childNumChildren = stoi(tokens[idx++]);
                NaryTreeNode* child = new NaryTreeNode(childVal);
                node->children.push_back(child);
                q.push(make_pair(child, childNumChildren));
            }
        }
        
        return root;
    }
    
private:
    vector<string> split(string data, string delimiter) {
        vector<string> tokens;
        size_t pos = 0;
        while ((pos = data.find(delimiter)) != string::npos) {
            tokens.push_back(data.substr(0, pos));
            data.erase(0, pos + delimiter.length());
        }
        if (!data.empty()) {
            tokens.push_back(data);
        }
        return tokens;
    }
};

int main() {
    Solution solution;
    
    // Test case: Create the tree from the example
    //       1
    //     / | \
    //    3  2  4
    //   / \
    //  5   6
    NaryTreeNode* root = new NaryTreeNode(1);
    NaryTreeNode* node3 = new NaryTreeNode(3);
    NaryTreeNode* node2 = new NaryTreeNode(2);
    NaryTreeNode* node4 = new NaryTreeNode(4);
    NaryTreeNode* node5 = new NaryTreeNode(5);
    NaryTreeNode* node6 = new NaryTreeNode(6);
    
    root->children = {node3, node2, node4};
    node3->children = {node5, node6};
    
    // Serialize
    string serialized = solution.serialize(root);
    cout << "Serialized: " << serialized << endl;
    
    // Deserialize
    NaryTreeNode* deserialized = solution.deserialize(serialized);
    
    // Verify by serializing again
    if (deserialized) {
        string reserialized = solution.serialize(deserialized);
        cout << "Reserialized: " << reserialized << endl;
        cout << "Match: " << (serialized == reserialized ? "Yes" : "No") << endl;
    }
    
    // Test empty tree
    string empty = solution.serialize(nullptr);
    cout << "Empty tree serialized: '" << empty << "'" << endl;
    NaryTreeNode* emptyDeserialized = solution.deserialize(empty);
    cout << "Empty tree deserialized: " << (emptyDeserialized == nullptr ? "nullptr" : "not nullptr") << endl;
    
    return 0;
}