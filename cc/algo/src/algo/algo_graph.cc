#include <climits>

#include "../include/fwd.h"

// Graph representation: vector<vector<pair<int, int>>>
// adj[u] = list of pairs (v, weight) representing edges from u to v with weight
// For unweighted graphs, use weight = 1
class AlgoGraph {
public:
    // Breadth First Search - works with weighted graph (ignores weights)
    void BreadthFirstSearch(int start_node, const vector<vector<pair<int, int>>>& adj) {
        queue<int> q;
        unordered_set<int> visited;

        q.push(start_node);
        visited.insert(start_node);

        while (!q.empty()) {
            int current = q.front();
            q.pop();
            // Process current node
            cout << "Visiting node: " << current << endl;
            for (const auto& edge : adj[current]) {
                int neighbor = edge.first;
                if (visited.find(neighbor) == visited.end()) {
                    visited.insert(neighbor);
                    q.push(neighbor);
                }
            }
        }
    }

    // Performs Topological Sort using Kahn's Algorithm
    // Returns an empty vector if a cycle is detected
    // Works with weighted graph (ignores weights for topological ordering)
    vector<int> TopologicalSort(int num_nodes, const vector<vector<pair<int, int>>>& adj) {
        vector<int> in_degree(num_nodes, 0);
        for (int i = 0; i < num_nodes; ++i) {
            for (const auto& edge : adj[i]) {
                int neighbor = edge.first;
                in_degree[neighbor]++;
            }
        }

        queue<int> q;
        for (int i = 0; i < num_nodes; ++i) {
            if (in_degree[i] == 0) {
                q.push(i);
            }
        }

        vector<int> topo_order;
        while (!q.empty()) {
            int u = q.front();
            q.pop();
            topo_order.push_back(u);

            for (const auto& edge : adj[u]) {
                int v = edge.first;
                if (--in_degree[v] == 0) {
                    q.push(v);
                }
            }
        }

        // If topo_order doesn't contain all nodes, there is a cycle
        if (topo_order.size() != static_cast<size_t>(num_nodes)) {
            return vector<int>();
        }
        return topo_order;
    }

    struct State {
        int node, dist;
        bool operator>(const State& other) const { return dist > other.dist; }
    };

    // Dijkstra's algorithm - uses edge weights
    int dijkstra(int start, int end, int n, const vector<vector<pair<int, int>>>& adj) {
        vector<int> dist(n, INT_MAX);
        priority_queue<State, vector<State>, greater<State>> pq;

        dist[start] = 0;
        State start_state;
        start_state.node = start;
        start_state.dist = 0;
        pq.push(start_state);

        while (!pq.empty()) {
            State curr = pq.top();
            pq.pop();

            if (curr.dist > dist[curr.node]) continue;
            if (curr.node == end) return curr.dist;

            for (const auto& edge : adj[curr.node]) {
                int nextNode = edge.first;
                int weight = edge.second;
                if (dist[curr.node] + weight < dist[nextNode]) {
                    dist[nextNode] = dist[curr.node] + weight;
                    State next_state;
                    next_state.node = nextNode;
                    next_state.dist = dist[nextNode];
                    pq.push(next_state);
                }
            }
        }
        return -1;
    }


};

class UnionFind {
public:
    vector<int> parent;
    int count; // Number of connected components
    UnionFind(int n) : count(n) {
        parent.resize(n);
        iota(parent.begin(), parent.end(), 0);
    }

    int find(int i) {
        if (parent[i] == i) return i;
        return parent[i] = find(parent[i]); // Path compression
    }

    void unite(int i, int j) {
        int rootI = find(i);
        int rootJ = find(j);
        if (rootI != rootJ) {
            parent[rootI] = rootJ;
            count--;
        }
    }
};

void kruskal(int n, vector<vector<pair<int, int>>>& adj) {
    UnionFind uf(n);
    priority_queue<pair<int, pair<int, int>>, vector<pair<int, pair<int, int>>>, greater<>> pq;
    for (int i = 0; i < n; i++) {
        for (const auto& edge : adj[i]) {
            pq.push({edge.second, {i, edge.first}});
        }
    }
    while (!pq.empty()) {
        auto [weight, edge] = pq.top();
        pq.pop();
        int u = edge.first;
        int v = edge.second;
        if (uf.find(u) != uf.find(v)) {
            uf.unite(u, v);
            cout << "Edge: " << u << " - " << v << " with weight " << weight << endl;
        }
    }
}

int main() {
    AlgoGraph graph;

    // Construct weighted graph: vector<vector<pair<int, int>>>
    // Each pair represents (neighbor, weight)
    // For unweighted graphs, use weight = 1
    int n = 6; // nodes 0-5
    vector<vector<pair<int, int>>> adj(n);

    // Example: directed graph with weighted edges
    // Node 0 -> Node 1 (weight 1), Node 0 -> Node 2 (weight 2)
    adj[0].push_back(make_pair(1, 1));
    adj[0].push_back(make_pair(2, 2));
    // Node 1 -> Node 2 (weight 3), Node 1 -> Node 3 (weight 4), Node 1 -> Node 5 (weight 5)
    adj[1].push_back(make_pair(2, 3));
    adj[1].push_back(make_pair(3, 4));
    adj[1].push_back(make_pair(5, 5));
    // Node 2 -> Node 3 (weight 1)
    adj[2].push_back(make_pair(3, 1));
    // Node 3 -> Node 4 (weight 2)
    adj[3].push_back(make_pair(4, 2));
    // Node 4 -> Node 1 (weight 1)  // creates a cycle
    adj[4].push_back(make_pair(1, 1));
    // Node 5 has no outgoing edges

    // Breadth First Search
    cout << "BFS starting from node 1:" << endl;
    graph.BreadthFirstSearch(1, adj);
    cout << endl;

    // Topological Sort
    vector<int> topo_order = graph.TopologicalSort(n, adj);
    if (topo_order.empty()) {
        cout << "Graph contains a cycle - no valid topological order" << endl;
    } else {
        cout << "Topological order: ";
        for (int node : topo_order) {
            cout << node << " ";
        }
        cout << endl;
    }
    cout << endl;

    // Dijkstra's algorithm
    int start = 1;
    int end = 4;
    int dist = graph.dijkstra(start, end, n, adj);
    if (dist == -1) {
        cout << "No path from " << start << " to " << end << endl;
    } else {
        cout << "Shortest distance from " << start << " to " << end << " is " << dist << endl;
    }

    return 0;
}