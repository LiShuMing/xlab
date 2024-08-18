#include "../include/fwd.h"

class Solution {
public:
    vector<int> findOrder(int numCourses, vector<vector<int>>& prerequisites) {
        vector<int> ans;
        vector<int> inDegree(numCourses, 0);
        unordered_map<int, vector<int>> graph;
        for (auto& prerequisite : prerequisites) {
            graph[prerequisite[1]].push_back(prerequisite[0]);
            inDegree[prerequisite[0]]++;
        }

        queue<int> q;
        for (int i = 0; i < numCourses; i++) {
            if (inDegree[i] == 0) q.push(i);
        }

        while (!q.empty()) {
            int course = q.front();
            q.pop();
            ans.push_back(course);
            for (auto& neighbor : graph[course]) {
                inDegree[neighbor]--;
                if (inDegree[neighbor] == 0) q.push(neighbor);
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