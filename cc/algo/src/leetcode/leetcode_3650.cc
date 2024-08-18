#include "../include/fwd.h"
class Solution {
public:
    int minCost(int n, vector<vector<int>>& edges) {
        // Build graph with asymmetric weights as per problem statement
        vector<vector<std::pair<int, int>>> g(n);
        for (auto &e : edges) {
            g[e[0]].push_back({e[1], e[2]});
            g[e[1]].push_back({e[0], e[2] * 2});
        }
        // Dijkstra's algorithm to find minimum cost
        priority_queue<std::pair<int, int>, vector<std::pair<int, int>>, greater<std::pair<int, int>>> q;
        q.emplace(0, 0);
        vector<int> dist(n, std::numeric_limits<int>::max());
        vector<bool> visited(n, false);
        dist[0] = 0;
        while (!q.empty()) {
            auto [d, u] = q.top();
            q.pop();
            if (u == n - 1) {
                return dist[u];
            }
            // Skip if this entry is stale (we've already found a better path)
            if (d > dist[u]) continue;
            // Skip if already processed
            if (visited[u]) continue;
            visited[u] = true;
            for (auto [v, w] : g[u]) {
                if (dist[v] > dist[u] + w) {
                    dist[v] = dist[u] + w;
                    q.emplace(dist[v], v);
                }
            }
        }
        return -1;
    }
};