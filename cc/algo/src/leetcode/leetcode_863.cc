#include "../include/fwd.h"

class Solution {
public:
    vector<int> distanceK(TreeNode* root, TreeNode* target, int k) {
        if (!root) return {};
        
        // Build bidirectional graph (parent <-> child)
        unordered_map<TreeNode*, vector<TreeNode*>> graph;
        function<void(TreeNode*, TreeNode*)> buildGraph = [&](TreeNode* node, TreeNode* parent) {
            if (!node) return;
            
            // Add bidirectional edges
            if (parent) {
                graph[node].push_back(parent);
                graph[parent].push_back(node);
            }
            
            if (node->left) {
                buildGraph(node->left, node);
            }
            if (node->right) {
                buildGraph(node->right, node);
            }
        };
        buildGraph(root, nullptr);
        
        // BFS to find nodes at distance k (more efficient and clearer)
        vector<int> ans;
        if (k == 0) {
            ans.push_back(target->val);
            return ans;
        }
        
        queue<pair<TreeNode*, int>> q;
        unordered_set<TreeNode*> visited;
        q.push({target, 0});
        visited.insert(target);
        
        while (!q.empty()) {
            auto [node, distance] = q.front();
            q.pop();
            
            if (distance == k) {
                ans.push_back(node->val);
                continue;  // Don't explore further from nodes at distance k
            }
            
            for (auto neighbor : graph[node]) {
                if (!visited.count(neighbor)) {
                    visited.insert(neighbor);
                    q.push({neighbor, distance + 1});
                }
            }
        }
        
        return ans;
    }
};

int main() {
    Solution solution;
    TreeNode* root = new TreeNode(3, new TreeNode(5, new TreeNode(6), new TreeNode(2, new TreeNode(7), new TreeNode(4))), new TreeNode(1, new TreeNode(0), new TreeNode(8)));
    TreeNode* target = root->left;
    int k = 2;
    vector<int> ans = solution.distanceK(root, target, k);
    printVector(ans);
    return 0;
}