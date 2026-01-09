#include "../include/fwd.h"

class Solution {
public:
    bool canFinish(int numCourses, vector<vector<int>>& prerequisites) {
        if (prerequisites.empty()) return true;
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
            for (auto& neighbor : graph[course]) {
                inDegree[neighbor]--;
                if (inDegree[neighbor] == 0) q.push(neighbor);
            }
        }
        for (int i = 0; i < numCourses; i++) {
            if (inDegree[i] != 0) return false;
        }
        return true;
    }
};

int main() {
    Solution solution;
    int numCourses = 2;
    vector<vector<int>> prerequisites = {{1, 0}};
    cout << solution.canFinish(numCourses, prerequisites) << endl;
    return 0;
}