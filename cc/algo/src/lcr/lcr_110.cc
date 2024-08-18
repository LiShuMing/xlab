#include "../include/fwd.h"

class Solution {
public:
    double bfs(unordered_map<string, unordered_map<string, double>>& graph, string start,
               string end) {
        if (graph.find(start) == graph.end() || graph.find(end) == graph.end()) {
            return -1.0;
        }
        queue<pair<string, double>> q;
        q.push({start, 1.0});
        unordered_set<string> visited;
        visited.insert(start);
        while (!q.empty()) {
            auto [node, value] = q.front();
            q.pop();
            if (node == end) {
                return value;
            }
            for (auto [neighbor, weight] : graph[node]) {
                if (!visited.count(neighbor)) {
                    visited.insert(neighbor);
                    q.push({neighbor, value * weight});
                }
            }
        }
        return -1.0;
    }

    vector<double> calcEquation(vector<vector<string>>& equations, vector<double>& values,
                                vector<vector<string>>& queries) {
        unordered_map<string, unordered_map<string, double>> graph;
        for (int i = 0; i < equations.size(); i++) {
            graph[equations[i][0]][equations[i][1]] = values[i];
            graph[equations[i][1]][equations[i][0]] = 1.0 / values[i];
        }
        vector<double> ans;
        for (int i = 0; i < queries.size(); i++) {
            ans.push_back(bfs(graph, queries[i][0], queries[i][1]));
        }
        return ans;
    }
};
int main() {
    Solution solution;
    vector<vector<string>> equations = {{"a", "b"}, {"b", "c"}};
    vector<double> values = {2.0, 3.0};
    vector<vector<string>> queries = {{"a", "c"}, {"b", "a"}, {"a", "e"}, {"a", "a"}, {"x", "x"}};
    vector<double> ans = solution.calcEquation(equations, values, queries);
    for (auto& a : ans) {
        cout << a << " ";
    }
    cout << endl;
    return 0;
}