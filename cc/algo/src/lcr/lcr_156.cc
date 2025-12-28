#include "../include/fwd.h"

class Codec {
public:
    // Encodes a tree to a single string.
    string serialize(TreeNode* root) {
        if (!root) return "null";
        // string ans;
        // queue<TreeNode*> q;
        // q.push(root);
        // while (!q.empty()) {
        //     TreeNode* node = q.front();
        //     q.pop();
        //     if (node) {
        //         ans += to_string(node->val) + ",";
        //     }
        // }
        // return ans;
        return serializeHelper(root);
    }
    string serializeHelper(TreeNode* root) {
        if (!root) return "null";
        return to_string(root->val) + "," + serializeHelper(root->left) + "," + serializeHelper(root->right);
    }

    // Decodes your encoded data to tree.
    TreeNode* deserialize(string data) {
        if (data.empty() || data == "null") return nullptr;
        vector<string> tokens = split(data, ",");
        int idx = 0;
        return deserializeHelper(tokens, idx);
    }
    TreeNode* deserializeHelper(const vector<string>& tokens, int& idx) {
        if (idx >= tokens.size() || tokens[idx] == "null") return nullptr;
        TreeNode* root = new TreeNode(stoi(tokens[idx]));
        root->left = deserializeHelper(tokens, ++idx);
        root->right = deserializeHelper(tokens, ++idx);
        return root;
    }
    vector<string> split(string data, string delimiter) {
        vector<string> tokens;
        size_t pos = 0;
        while ((pos = data.find(delimiter)) != string::npos) {
            tokens.push_back(data.substr(0, pos));
            data.erase(0, pos + delimiter.length());
        }
        return tokens;
    }
};
int main() {
    Codec codec;
    TreeNode* root = new TreeNode(1, new TreeNode(2), new TreeNode(3));
    string serialized = codec.serialize(root);
    cout << "Serialized: " << serialized << endl;
    TreeNode* deserialized = codec.deserialize(serialized);
    cout << "Deserialized: " << deserialized->val << endl;
    return 0;
}