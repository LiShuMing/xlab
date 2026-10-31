#include "../include/fwd.h"

/**
* 给你一个大小为 n x n 的二元矩阵 grid ，其中 1 表示陆地，0 表示水域。
* 岛 是由四面相连的 1 形成的一个最大组，即不会与非组内的任何其他 1 相连。grid 中 恰好存在两座岛 。
* 你可以将任意数量的 0 变为 1 ，以使两座岛连接起来，变成 一座岛 。
* 返回必须翻转的 0 的最小数目。
*/
// 思路：答案 = 两座岛之间最短路径上「被穿过的 0」的个数。
//
//   第一步：从任意一个 1 出发，把它所在的整座岛泛洪染成 2（2 兼作已访问标记），
//           顺手把岛上的格子压进队列，它们就是 BFS 的第 0 层。
//   第二步：多源 BFS，每向外扩一层就相当于多翻一个 0；
//           第一次碰到另一座 1 时，当前层号（已经翻过的 0 的个数）就是答案。
//
//   [[0,1],     岛 A = 右上，岛 B = 左下
//    [1,0]]     A 的邻居 (0,0) 紧挨着 B ⇒ 翻 1 个 0 就连通 ⇒ 答案 1
//
//   复杂度：O(n^2) 时间（每格最多入队一次），O(n^2) 空间（队列）。
//   易错点：起点必须是「整座岛」而不是第一个扫到的 1。
//          只从单个格子做单源 BFS 会绕远路，答案偏大（见 main 里的第 3 组用例）。
class Solution {
public:
    int shortestBridge(vector<vector<int>>& grid) {
        rows_ = static_cast<int>(grid.size());
        cols_ = static_cast<int>(grid[0].size());

        // 找准入队完成：染完整座岛后队列就不空了，用 q.empty() 当开关，
        // 两层循环自然收敛，不会误把第二座岛也染了。
        queue<pair<int, int>> q;
        for (int i = 0; i < rows_ && q.empty(); ++i) {
            for (int j = 0; j < cols_ && q.empty(); ++j) {
                if (grid[i][j] == 1) paint(grid, i, j, q);
            }
        }

        // 多源 BFS：队列里这一层都是「已经翻过 dist 个 0」才走到的格子。
        int dist = 0;
        while (!q.empty()) {
            for (int k = static_cast<int>(q.size()); k > 0; --k) {
                const auto [x, y] = q.front();
                q.pop();
                for (const auto& d : kDirs) {
                    const int nx = x + d[0];
                    const int ny = y + d[1];
                    if (nx < 0 || nx >= rows_ || ny < 0 || ny >= cols_) continue;  // 出界
                    if (grid[nx][ny] == 2) continue;  // 自家岛内部，或已经走过的水
                    // 碰到另一座岛：当前格子这一层的层号就是答案（本层的格子只翻过 dist 个 0）。
                    if (grid[nx][ny] == 1) return dist;
                    // 是水：翻转它才能走过去，染成 2 表示「已访问」，下一层再扩。
                    grid[nx][ny] = 2;
                    q.push({nx, ny});
                }
            }
            ++dist;  // 这一层扩完，下一层的每个格子都多翻了一个 0
        }
        return -1;  // 题目保证恰好两座岛，正常不会走到这里
    }

private:
    static constexpr int kDirs[4][2] = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
    int rows_ = 0;
    int cols_ = 0;

    // 把 (sx, sy) 所在的整座岛染成 2，并把岛上的格子全部压进 q（作为 BFS 的第 0 层）。
    // 用显式栈而不是递归 DFS：岛可能是一条 1 万格的长蛇，递归在 Windows 的 1MB 默认栈上不安全。
    void paint(vector<vector<int>>& grid, int sx, int sy, queue<pair<int, int>>& q) {
        stack<pair<int, int>> st;
        st.push({sx, sy});
        grid[sx][sy] = 2;  // 入栈即染色：保证每个格子只入栈一次，不会被重复染色

        while (!st.empty()) {
            const auto [x, y] = st.top();
            st.pop();
            q.push({x, y});
            for (const auto& d : kDirs) {
                const int nx = x + d[0];
                const int ny = y + d[1];
                if (nx < 0 || nx >= rows_ || ny < 0 || ny >= cols_) continue;  // 出界
                if (grid[nx][ny] != 1) continue;  // 0 是水（不连），2 是已经染过的同伴
                grid[nx][ny] = 2;
                st.push({nx, ny});
            }
        }
    }
};

int main() {
    // 注意：shortestBridge 会就地修改 grid（把走过的格子染成 2），
    // 所以每组用例都在下面拷贝一份再传进去，保证可以重复执行。
    const struct {
        vector<vector<int>> grid;
        int expect;
        const char* note;
    } cases[] = {
        {{{0, 1}, {1, 0}}, 1, "两岛斜对角，翻 1 个 0"},
        {{{0, 1, 0}, {0, 0, 0}, {0, 0, 1}}, 2, "必须连续穿过两个 0"},
        // 这组专门抓「起点退化成单个格子」的错：只从先扫到的 (0,0) 出发会得到 2，
        // 而从岛上的 (0,2) 出发翻 (1,2) 就够，所以正确答案是 1。
        {{{1, 1, 1}, {1, 0, 0}, {0, 0, 1}}, 1, "多源起点：单源会算成 2"},
        {{{1, 1, 1, 1, 1},
          {1, 0, 0, 0, 1},
          {1, 0, 1, 0, 1},
          {1, 0, 0, 0, 1},
          {1, 1, 1, 1, 1}},
         1,
         "内岛被一圈 0 包住"},
        {{{1, 0, 0, 1}}, 2, "一条线上两头各一座岛"},
        // 大距离用例：两座单格岛在对角，必须真的走完一条 8 步的长路（中间穿过 7 个 0）。
        {{{1, 0, 0, 0, 0},
          {0, 0, 0, 0, 0},
          {0, 0, 0, 0, 0},
          {0, 0, 0, 0, 0},
          {0, 0, 0, 0, 1}},
         7,
         "对角两座单格岛，层数要数对"},
    };

    Solution solution;
    int failed = 0;
    for (const auto& c : cases) {
        auto grid = c.grid;
        const int got = solution.shortestBridge(grid);
        cout << "shortestBridge = " << got << "  expect " << c.expect
             << (got == c.expect ? "  OK" : "  FAIL") << "  [" << c.note << "]" << endl;
        if (got != c.expect) ++failed;
    }
    cout << (failed == 0 ? "leetcode_934: all checks passed" : "leetcode_934: FAILED") << endl;
    return failed == 0 ? 0 : 1;
}
