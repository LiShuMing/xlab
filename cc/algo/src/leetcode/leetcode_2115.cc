#include "../include/fwd.h"

class Solution {
public:
    vector<string> findAllRecipes(vector<string>& recipes, vector<vector<string>>& ingredients, vector<string>& supplies) {
        unordered_set<string> supply_set(supplies.begin(), supplies.end());
        // Build the graph
        // graph[ingredient] = list of recipes
        unordered_map<string, vector<string>> graph;
        unordered_map<string, int> in_degree;

        int n = recipes.size();
        for (int i = 0; i < n; i++) {
            auto recipe = recipes[i];
            in_degree[recipes[i]] = 0;
            for (string ingredient : ingredients[i]) {
                graph[ingredient].push_back(recipe);
                // since supply_set contains all supplies,
                // we only need to check if the ingredient is not in the supply_set
                if (supply_set.find(ingredient) == supply_set.end()) {
                    in_degree[recipe]++;
                }
            }
        }

        queue<string> q;
        // for (string supply : supplies) {
        //     q.push(supply);
        // }
        for (auto& recipe : recipes) {
            if (in_degree[recipe] == 0) {
                q.push(recipe);
            }
        }
        vector<string> ans;
        while (!q.empty()) {
            string node = q.front();
            q.pop();
            auto it = graph.find(node);
            if (it == graph.end()) {
                continue;
            }

            for (auto& neighbor : it->second) {
                in_degree[neighbor]--;
                if (in_degree[neighbor] == 0) {
                    q.push(neighbor);
                }
            }
        }
        for (string recipe : recipes) {
            if (in_degree[recipe] == 0) {
                ans.push_back(recipe);
            }
        }
        return ans;
    }
};
