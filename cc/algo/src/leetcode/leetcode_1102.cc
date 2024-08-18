#include "../include/fwd.h"
#include <climits>

class Solution {
public:
    /**
    * Given an m x n matrix A, return the maximum score of a path starting at (0, 0) and ending at (m-1, n-1).
    * The score of a path is the minimum value in that path.
    * You can move in 4 directions (up, down, left, right).
    */
    int maximumMinimumPath(vector<vector<int>>& grid) {
        int n = grid.size();
        if (n == 0) return 0;
        int m = grid[0].size();
        if (m == 0) return 0;

        // use binary search to find the maximum minimum value of a path
        int min_value = INT_MAX;
        int max_value = INT_MIN;
        for (int i = 0; i < n; i++) {
            for (int j = 0; j < m; j++) {
                min_value = min(min_value, grid[i][j]);
                max_value = max(max_value, grid[i][j]);
            }
        }
        
        // Binary search: find the maximum value such that canReach(value) is true
        // If canReach(mid) is true, we can try a higher value (left = mid + 1)
        // If canReach(mid) is false, we need a lower value (right = mid - 1)
        int left = min_value;
        int right = max_value;
        int result = min_value;
        
        while (left <= right) {
            int mid = left + (right - left) / 2;
            if (canReach(grid, mid)) {
                result = mid;  // This value works, try to find a higher one
                left = mid + 1;
            } else {
                right = mid - 1;
            }
        }
        return result;
    }

    bool canReach(vector<vector<int>>& grid, int value) {
        int n = grid.size();
        int m = grid[0].size();
        
        // Check if start and end cells meet the minimum value requirement
        if (grid[0][0] < value || grid[n - 1][m - 1] < value) {
            return false;
        }
        
        vector<vector<bool>> visited(n, vector<bool>(m, false));
        queue<pair<int, int> > q;
        q.push(make_pair(0, 0));
        visited[0][0] = true;
        vector<pair<int, int>> dirs;
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
                if (nx >= 0 && nx < n && ny >= 0 && ny < m && !visited[nx][ny] && grid[nx][ny] >= value) {
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
    vector<vector<int>> grid;
    grid.push_back(vector<int>());
    grid[0].push_back(5);
    grid[0].push_back(4);
    grid[0].push_back(5);
    grid.push_back(vector<int>());
    grid[1].push_back(1);
    grid[1].push_back(2);
    grid[1].push_back(6);
    grid.push_back(vector<int>());
    grid[2].push_back(7);
    grid[2].push_back(4);
    grid[2].push_back(6);
    cout << solution.maximumMinimumPath(grid) << endl;
    return 0;
}