#include "../include/fwd.h"

/**
 * @brief 200. 岛屿数量
 * 给你一个由 '1'（陆地）和 '0'（水）组成的的二维网格，请你计算网格中岛屿的数量。
 * 岛屿总是被水包围，并且每座岛屿只能由水平方向和/或竖直方向上相邻的陆地连接形成。
 * 此外，你可以假设该网格的四条边均被水包围。
 */
class Solution {
public:
    int numIslands(vector<vector<char>>& grid) {
        int ans = 0;
        for (int i = 0; i < grid.size(); i++) {
            for (int j = 0; j < grid[0].size(); j++) {
                if (grid[i][j] == '1') {
                    ans++;
                    bfs(grid, i, j);
                }
            }
        }
        return ans;
    }

    void bfs(vector<vector<char>>& grid, int i, int j) {
        // 使用队列实现 BFS
        queue<pair<int, int>> q;
        q.push({i, j});
        while (!q.empty()) {
            pair<int, int> p = q.front();
            q.pop();
            i = p.first;
            j = p.second;
            if (i < 0 || i >= grid.size() || j < 0 || j >= grid[0].size() || grid[i][j] == '0') {
                continue;
            }
            grid[i][j] = '0';
            q.push({i + 1, j});
            q.push({i - 1, j});
            q.push({i, j + 1});
            q.push({i, j - 1});
        }
    }

};
