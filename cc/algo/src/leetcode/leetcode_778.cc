#include "../include/fwd.h"
#include <climits>

class Solution {
public:
    // 1. use binary search to find the minimum time to swim in water
    // 2. use bfs/dfs   
    int swimInWater(vector<vector<int>>& grid) {
        int n = grid.size();
        if (n == 0) return 0;
        int m = grid[0].size();
        if (m == 0) return 0;

        int max_value = 0;
        for (int i = 0; i < n; i++) {
            for (int j = 0; j < m; j++) {
                max_value = max(max_value, grid[i][j]);
            }
        }
        
        // The minimum time needed is at least max(grid[0][0], grid[n-1][m-1])
        // because we must wait for both start and end cells to be accessible
        int left = max(grid[0][0], grid[n-1][m-1]);
        int right = max_value;
        int result = right;
        
        // Binary search: find the minimum time such that canSwim(time) is true
        // If canSwim(mid) is true, we can try a lower time (right = mid)
        // If canSwim(mid) is false, we need a higher time (left = mid + 1)
        while (left <= right) {
            int mid = left + (right - left) / 2;
            if (canSwim(grid, mid)) {
                result = mid;  // This time works, try to find a lower one
                right = mid - 1;
            } else {
                left = mid + 1;
            }
        }
        return result;
    }

    bool canSwim(vector<vector<int>>& grid, int time) {
        int n = grid.size();
        int m = grid[0].size();
        
        // Check if start cell is accessible at the given time
        if (grid[0][0] > time) {
            return false;
        }
        
        vector<vector<bool> > visited(n, vector<bool>(m, false));
        queue<pair<int, int> > q;
        q.push(make_pair(0, 0));
        visited[0][0] = true;
        
        vector<pair<int, int> > dirs;
        dirs.push_back(make_pair(0, 1));
        dirs.push_back(make_pair(1, 0));
        dirs.push_back(make_pair(-1, 0));
        dirs.push_back(make_pair(0, -1));
        
        while (!q.empty()) {
            pair<int, int> curr = q.front();
            q.pop();
            int x = curr.first;
            int y = curr.second;
            
            if (x == n - 1 && y == m - 1) {
                return true;
            }
            
            for (size_t i = 0; i < dirs.size(); i++) {
                int nx = x + dirs[i].first;
                int ny = y + dirs[i].second;
                if (nx >= 0 && nx < n && ny >= 0 && ny < m && !visited[nx][ny] && grid[nx][ny] <= time) {
                    q.push(make_pair(nx, ny));
                    visited[nx][ny] = true;
                }
            }
        }
        return false;
    }
};

int main() {
    Solution solution;
    vector<vector<int> > grid;
    grid.push_back(vector<int>());
    grid[0].push_back(3);
    grid[0].push_back(2);
    grid.push_back(vector<int>());
    grid[1].push_back(0);
    grid[1].push_back(1);
    
    cout << "grid: ";
    for (size_t i = 0; i < grid.size(); i++) {
        for (size_t j = 0; j < grid[i].size(); j++) {
            cout << grid[i][j] << " ";
        }
        cout << endl;
    }
    cout << "ans: " << solution.swimInWater(grid) << endl;
    return 0;
}