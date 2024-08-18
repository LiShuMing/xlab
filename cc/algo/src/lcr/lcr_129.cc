#include "../include/fwd.h"
class Solution {
public:
    bool wordPuzzle(vector<vector<char>>& grid, string target) {
        int n = grid.size();
        int m = grid[0].size();
        for (int i = 0; i < n; i++) {
            for (int j = 0; j < m; j++) {
                if (dfs(grid, target, i, j, 0)) return true;
            }
        }
        return false;
    }
    bool dfs(vector<vector<char>>& grid, string target, int i, int j, int k) {
        if (k == target.size()) return true;
        if (i < 0 || i >= grid.size() || j < 0 || j >= grid[0].size()) return false;
        if (grid[i][j] != target[k]) return false;
        char temp = grid[i][j];
        grid[i][j] = '#';
        vector<pair<int, int>> dirs = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
        for (auto& dir : dirs) {
            int x = i + dir.first;
            int y = j + dir.second;
            if (dfs(grid, target, x, y, k + 1)) return true;
        }
        grid[i][j] = temp;
        return false;
    }
};
int main() {
    Solution solution;
    vector<vector<char>> grid = {{'a', 'b', 'c'}, {'d', 'e', 'f'}, {'g', 'h', 'i'}};
    string target = "abcdefghi";
    cout << solution.wordPuzzle(grid, target) << endl;
    return 0;
}