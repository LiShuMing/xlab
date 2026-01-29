#include "../include/fwd.h"

class Solution {
public:
    // Helper function to find minimum cost between two characters using Dijkstra's algorithm
    int findMinCost(int src, int dst, const vector<vector<pair<int, int>>>& g) {
        if (src == dst) return 0;
        priority_queue<pair<int, int>, vector<pair<int, int>>, greater<>> pq;
        vector<int> dist(26, numeric_limits<int>::max());
        pq.push({0, src});
        dist[src] = 0;
        while (!pq.empty()) {
            auto [d, u] = pq.top();
            pq.pop();
            if (d != dist[u]) continue;
            if (u == dst) return d;
            for (auto [v, w] : g[u]) {
                if (dist[v] > d + w) {
                    dist[v] = d + w;
                    pq.push({dist[v], v});
                }
            }
        }
        return numeric_limits<int>::max();
    }

    long long minimumCost(string source, string target, vector<char>& original,
                          vector<char>& changed, vector<int>& cost) {
        // use greedy algorithm to solve the problem

        // build a graph
        vector<vector<pair<int, int>>> g(26);
        for (int i = 0; i < original.size(); i++) {
            g[original[i] - 'a'].push_back({changed[i] - 'a', cost[i]});
        }
        // iterate the source string
        long long ans = 0;
        // add a cache to store the minimum cost to transform the current character to the target character
        // key: src * 26 + dst (encodes pair<char, char> as int)
        unordered_map<int, int> cache;
        for (int i = 0; i < source.size(); i++) {
            // find the minimum cost to transform the current character to the target character
            int key = (source[i] - 'a') * 26 + (target[i] - 'a');
            if (cache.find(key) != cache.end()) {
                ans += cache[key];
            } else {
                int min_cost = findMinCost(source[i] - 'a', target[i] - 'a', g);
                cache[key] = min_cost;
                if (min_cost == numeric_limits<int>::max()) {
                    return -1;
                }
                ans += min_cost;
            }
        }
        return ans;
    }
};