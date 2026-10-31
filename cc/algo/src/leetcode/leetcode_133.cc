#include "../include/fwd.h"

class Node {
public:
    int val;
    vector<Node*> neighbors;
    Node(int _val) : val(_val) {}
};

// class Solution {
// public:
//     Node* cloneGraph(Node* node) {
//         if (!node) return nullptr;
//         unordered_map<Node*, Node*> map;
//         set<Node*> visited;
//         return dfs(node, map, visited);
//     }
//     Node* dfs(Node* node, unordered_map<Node*, Node*>& map, set<Node*>& visited) {
//         if (!node) return nullptr;
//         if (visited.find(node) != visited.end()) return map[node];
//         visited.insert(node);
//         map[node] = new Node(node->val);
//         for (auto neighbor : node->neighbors) {
//             map[node]->neighbors.push_back(dfs(neighbor, map, visited));
//         }
//         return map[node];
//     }
// };

/*
// Definition for a Node.
class Node {
public:
    int val;
    vector<Node*> neighbors;
    Node() {
        val = 0;
        neighbors = vector<Node*>();
    }
    Node(int _val) {
        val = _val;
        neighbors = vector<Node*>();
    }
    Node(int _val, vector<Node*> _neighbors) {
        val = _val;
        neighbors = _neighbors;
    }
};
*/

class Solution {
public:
    Node* cloneGraph(Node* node) {
        if (!node) {
            return nullptr;
        }
        unordered_map<Node*, Node*> visited;
        return dfs(node, visited);
    }

    /*
     */
    Node* dfs(Node* r, unordered_map<Node*, Node*>& visited) {
        if (!r) {
            return nullptr;
        }
        if (visited.find(r) != visited.end()) {
            return visited[r];
        }
        Node* node = new Node(r->val);
        visited[r] = node;
        for (auto* ng: r->neighbors) {
            node->neighbors.push_back(dfs(ng, visited));
        }
        return node;
    }
};

int main() {
    Solution solution;
    Node* node = new Node(1);
    node->neighbors.push_back(new Node(2));
    node->neighbors.push_back(new Node(3));
    Node* ans = solution.cloneGraph(node);
    cout << ans->val << " ";
    cout << endl;
    return 0;
}
