#include "../include/fwd.h"

class Solution {
public:
    vector<int> findOrder(int numCourses, vector<vector<int>>& prerequisites) {
        vector<int> ans;
        vector<int> in_degree(numCourses, 0);
        unordered_map<int, vector<int>> graph;
        for (auto& prerequisite : prerequisites) {
            int cur = prerequisite[0];
            int next = prerequisite[1];
            graph[next].push_back(cur);
            in_degree[cur]++;
        }

        queue<int> q;
        for (int i = 0; i < numCourses; i++) {
            if (in_degree[i] == 0) q.push(i);
        }

        while (!q.empty()) {
            int course = q.front();
            q.pop();
            ans.push_back(course);
            for (auto& neighbor : graph[course]) {
                in_degree[neighbor]--;
                if (in_degree[neighbor] == 0) q.push(neighbor);
            }
        }
        if (ans.size() == numCourses) return ans;
        return {};
    }
};

int main() {
    Solution solution;
    int numCourses = 2;
    vector<vector<int>> prerequisites = {{1, 0}};
    vector<int> ans = solution.findOrder(numCourses, prerequisites);
    for (auto& a : ans) {
        cout << a << " ";
    }
    cout << endl;
    return 0;
}
