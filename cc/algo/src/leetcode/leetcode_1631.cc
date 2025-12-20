#include "../include/fwd.h"
#include <climits>

class Solution {
public:
    int minimumEffortPath(vector<vector<int>>& heights) {
        int n = heights.size();
        if (n == 0) return 0;
        int m = heights[0].size();
        if (m == 0) return 0;

        int min_value = INT_MAX;
        int max_value = INT_MIN;
        for (int i = 0; i < n; i++) {
            for (int j = 0; j < m; j++) {
                min_value = min(min_value, heights[i][j]);
                max_value = max(max_value, heights[i][j]);
            }
        }
        
        // Effort is the absolute difference between adjacent cells
        // So it ranges from 0 to (max_value - min_value)
        int left = 0;
        int right = max_value - min_value;
        int result = right;
        
        // Binary search: find the minimum effort such that canReach(effort) is true
        // If canReach(mid) is true, we can try a lower effort (right = mid - 1)
        // If canReach(mid) is false, we need a higher effort (left = mid + 1)
        while (left <= right) {
            int mid = left + (right - left) / 2;
            if (canReach(heights, mid)) {
                result = mid;  // This effort works, try to find a lower one
                right = mid - 1;
            } else {
                left = mid + 1;
            }
        }
        return result;
    }

    bool canReach(vector<vector<int>>& heights, int max_effort) {
        int n = heights.size();
        int m = heights[0].size();
        
        vector<vector<bool> > visited(n, vector<bool>(m, false));
        queue<pair<int, int> > q;
        q.push(make_pair(0, 0));
        visited[0][0] = true;
        
        vector<pair<int, int> > dirs = {{0, 1}, {1, 0}, {-1, 0}, {0, -1}};
        
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
                if (nx >= 0 && nx < n && ny >= 0 && ny < m && !visited[nx][ny]) {
                    int effort = abs(heights[nx][ny] - heights[x][y]);
                    if (effort <= max_effort) {
                        q.push(make_pair(nx, ny));
                        visited[nx][ny] = true;
                    }
                }
            }
        }
        return false;
    }
};

int main() {
    Solution solution;
    
    // Test case 1
    vector<vector<int> > heights = {{1, 2, 2}, {3, 8, 2}, {5, 3, 5}};
    cout << "Test 1: " << solution.minimumEffortPath(heights) << endl;
    
    // Test case 2
    vector<vector<int> > heights2 = {{1, 2, 3}, {3, 8, 4}, {5, 3, 5}};
    cout << "Test 2: " << solution.minimumEffortPath(heights2) << endl;
    
    return 0;
}