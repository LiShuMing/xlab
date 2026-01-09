#include "../include/fwd.h"

class Node {
public:
    int val;
    vector<Node*> neighbors;
    Node(int _val) : val(_val) {}
};

class Solution {
public:
    Node* cloneGraph(Node* node) {
        if (!node) return nullptr;
        unordered_map<Node*, Node*> map;
        set<Node*> visited;
        return dfs(node, map, visited);
    }
    Node* dfs(Node* node, unordered_map<Node*, Node*>& map, set<Node*>& visited) {
        if (!node) return nullptr;
        if (visited.find(node) != visited.end()) return map[node];
        visited.insert(node);
        map[node] = new Node(node->val);
        for (auto neighbor : node->neighbors) {
            map[node]->neighbors.push_back(dfs(neighbor, map, visited));
        }
        return map[node];
    }
};
int main() {
    Solution solution;
    Node* node = new Node(1);
    node->neighbors.push_back(new Node(2));
    node->neighbors.push_back(new Node(3));
    vector<Node*> ans = solution.cloneGraph(node);
    for (auto& a : ans) {
        cout << a->val << " ";
    }
    cout << endl;
    return 0;
}