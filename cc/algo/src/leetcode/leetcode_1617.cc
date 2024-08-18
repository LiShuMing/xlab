#include "../include/fwd.h"

class Solution {
private:
    bool isConnected(int subset, const vector<vector<int> >& adj, int n) {
        int start = -1;
        for (int i = 0; i < n; i++) {
            if (subset & (1 << i)) {
                start = i;
                break;
            }
        }
        if (start == -1) return false;
        
        vector<int> visited(n, 0);
        queue<int> q;
        q.push(start);
        visited[start] = 1;
        int count = 0;
        
        while (!q.empty()) {
            int u = q.front();
            q.pop();
            count++;
            for (int v = 0; v < n; v++) {
                if (adj[u][v] && (subset & (1 << v)) && !(visited[v])) {
                    visited[v] = 1;
                    q.push(v);
                }
            }
        }
        
        int nodeCount = 0;
        for (int i = 0; i < n; i++) {
            if (subset & (1 << i)) nodeCount++;
        }
        
        return count == nodeCount;
    }
    
    int getDiameter(int subset, const vector<vector<int> >& adj, int n) {
        int start = -1;
        for (int i = 0; i < n; i++) {
            if (subset & (1 << i)) {
                start = i;
                break;
            }
        }
        if (start == -1) return 0;
        
        queue<int> q;
        vector<int> dist(n, -1);
        q.push(start);
        dist[start] = 0;
        int farNode = start;
        
        while (!q.empty()) {
            int u = q.front();
            q.pop();
            farNode = u;
            for (int v = 0; v < n; v++) {
                if (adj[u][v] && (subset & (1 << v)) && dist[v] == -1) {
                    dist[v] = dist[u] + 1;
                    q.push(v);
                }
            }
        }
        
        vector<int> dist2(n, -1);
        q.push(farNode);
        dist2[farNode] = 0;
        int maxDist = 0;
        
        while (!q.empty()) {
            int u = q.front();
            q.pop();
            maxDist = max(maxDist, dist2[u]);
            for (int v = 0; v < n; v++) {
                if (adj[u][v] && (subset & (1 << v)) && dist2[v] == -1) {
                    dist2[v] = dist2[u] + 1;
                    q.push(v);
                }
            }
        }
        
        return maxDist;
    }
    
public:
    vector<int> countSubgraphsForEachDiameter(int n, vector<vector<int> >& edges) {
        vector<int> ans(n - 1, 0);
        
        vector<vector<int> > adj(n, vector<int>(n, 0));
        for (int i = 0; i < edges.size(); i++) {
            int u = edges[i][0] - 1;
            int v = edges[i][1] - 1;
            adj[u][v] = adj[v][u] = 1;
        }
        
        int total = 1 << n;
        // Include full set (all nodes) - a tree is also a valid subtree
        for (int subset = 1; subset < total; subset++) {
            if (!isConnected(subset, adj, n)) continue;
            
            int diameter = getDiameter(subset, adj, n);
            
            if (diameter >= 1 && diameter <= n - 1) {
                ans[diameter - 1]++;
            }
        }
        
        return ans;
    }
};

int main() {
    Solution solution;
    
    // Test case 1: Star shape 1-2, 1-3, 1-4
    int n1 = 4;
    int e1[][2] = {{1, 2}, {1, 3}, {1, 4}};
    vector<vector<int> > edges1(3, vector<int>(2));
    for (int i = 0; i < 3; i++) {
        edges1[i][0] = e1[i][0];
        edges1[i][1] = e1[i][1];
    }
    vector<int> ans1 = solution.countSubgraphsForEachDiameter(n1, edges1);
    cout << "Test 1 star [1-2,1-3,1-4]: ";
    for (int i = 0; i < ans1.size(); i++) {
        cout << ans1[i] << " ";
    }
    cout << endl;
    
    // Test case 2: Line 1-2-3-4
    int n2 = 4;
    int e2[][2] = {{1, 2}, {2, 3}, {3, 4}};
    vector<vector<int> > edges2(3, vector<int>(2));
    for (int i = 0; i < 3; i++) {
        edges2[i][0] = e2[i][0];
        edges2[i][1] = e2[i][1];
    }
    vector<int> ans2 = solution.countSubgraphsForEachDiameter(n2, edges2);
    cout << "Test 2 line [1-2,2-3,3-4]: ";
    for (int i = 0; i < ans2.size(); i++) {
        cout << ans2[i] << " ";
    }
    cout << endl;
    
    // Manual verification for line:
    // Diameter 1: [1,2], [2,3], [3,4] -> 3
    // Diameter 2: [1,2,3], [2,3,4] -> 2
    // Diameter 3: [1,2,3,4] -> 1
    cout << "Expected line: 3 2 1" << endl;
    
    return 0;
}
