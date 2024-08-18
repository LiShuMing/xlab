#include "../include/fwd.h"

/**
 * Definition for a binary tree node.
 * struct TreeNode {
 *     int val;
 *     TreeNode *left;
 *     TreeNode *right;
 *     TreeNode(int x) : val(x), left(NULL), right(NULL) {}
 * };
 */
class Codec {
public:
    // Encodes a tree to a single string.
    string serialize(TreeNode* root) {
        if (!root) return "null";
        string ans;
        queue<TreeNode*> q;
        q.push(root);
        while (!q.empty()) {
            TreeNode* node = q.front();
            q.pop();
            if (node) {
                ans += to_string(node->val) + ",";
                q.push(node->left);
                q.push(node->right);
            } else {
                ans += "null,";
            }
        }
        // Remove trailing comma
        if (!ans.empty() && ans.back() == ',') {
            ans.pop_back();
        }
        return ans;
    }

    // Decodes your encoded data to tree.
    TreeNode* deserialize(string data) {
        if (data.empty() || data == "null") return nullptr;
        vector<string> tokens = split(data, ",");
        if (tokens.empty() || tokens[0] == "null") return nullptr;
        
        TreeNode* root = new TreeNode(stoi(tokens[0]));
        queue<TreeNode*> q;
        q.push(root);
        int idx = 1;
        
        while (!q.empty() && idx < tokens.size()) {
            TreeNode* node = q.front();
            q.pop();
            
            // Left child
            if (idx < tokens.size()) {
                if (tokens[idx] != "null") {
                    node->left = new TreeNode(stoi(tokens[idx]));
                    q.push(node->left);
                }
                idx++;
            }
            
            // Right child
            if (idx < tokens.size()) {
                if (tokens[idx] != "null") {
                    node->right = new TreeNode(stoi(tokens[idx]));
                    q.push(node->right);
                }
                idx++;
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

// Your Codec object will be instantiated and called as such:
// Codec ser, deser;
// TreeNode* ans = deser.deserialize(ser.serialize(root));
int main() {
    Codec codec;
    
    // Test case 1: Simple tree
    TreeNode* root = new TreeNode(1, new TreeNode(2), new TreeNode(3));
    string serialized = codec.serialize(root);
    cout << "Serialized: " << serialized << endl;
    TreeNode* deserialized = codec.deserialize(serialized);
    if (deserialized) {
        cout << "Deserialized root: " << deserialized->val << endl;
        if (deserialized->left) cout << "Left: " << deserialized->left->val << endl;
        if (deserialized->right) cout << "Right: " << deserialized->right->val << endl;
        
        // Verify by serializing again
        string reserialized = codec.serialize(deserialized);
        cout << "Reserialized: " << reserialized << endl;
        cout << "Match: " << (serialized == reserialized ? "Yes" : "No") << endl;
    }
    
    // Test case 2: Tree with null nodes
    TreeNode* root2 = new TreeNode(1, 
                                   new TreeNode(2, nullptr, new TreeNode(4)), 
                                   new TreeNode(3));
    string serialized2 = codec.serialize(root2);
    cout << "\nSerialized (with nulls): " << serialized2 << endl;
    TreeNode* deserialized2 = codec.deserialize(serialized2);
    if (deserialized2) {
        string reserialized2 = codec.serialize(deserialized2);
        cout << "Reserialized: " << reserialized2 << endl;
        cout << "Match: " << (serialized2 == reserialized2 ? "Yes" : "No") << endl;
    }
    
    // Test case 3: Empty tree
    string empty = codec.serialize(nullptr);
    cout << "\nEmpty tree serialized: '" << empty << "'" << endl;
    TreeNode* emptyDeserialized = codec.deserialize(empty);
    cout << "Empty tree deserialized: " << (emptyDeserialized == nullptr ? "nullptr" : "not nullptr") << endl;
    
    return 0;
}