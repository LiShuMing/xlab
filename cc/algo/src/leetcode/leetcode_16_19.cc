#include "../include/fwd.h"

class Solution {
public:
    vector<int> pondSizes(vector<vector<int>>& land) {
        int n = land.size();
        int m = land[0].size();
        vector<int> sizes;
        for (int i = 0; i < n; i++) {
            for (int j = 0; j < m; j++) {
                if (land[i][j] == 0) {
                    size_t size = 0;
                    dfs(land, i, j, size);
                    sizes.push_back(size);
                }
            }
        }
        sort(sizes.begin(), sizes.end());
        return sizes;
    }

    void dfs(vector<vector<int>>& land, int i, int j, size_t& size) {
        if (i < 0 || i >= land.size() || j < 0 || j >= land[0].size() || land[i][j] != 0) {
            return;
        }
        land[i][j] = -1;
        size++;
        dfs(land, i + 1, j, size);
        dfs(land, i - 1, j, size);
        dfs(land, i, j + 1, size);
        dfs(land, i, j - 1, size);
        dfs(land, i + 1, j + 1, size);
        dfs(land, i - 1, j + 1, size);
        dfs(land, i + 1, j - 1, size);
        dfs(land, i - 1, j - 1, size);
    }
};

int main() {
    Solution solution;
    vector<vector<int>> land = {{0, 2, 1, 0}, {0, 1, 0, 1}, {1, 1, 0, 1}, {0, 1, 0, 1}};
    vector<int> sizes = solution.pondSizes(land);
    for (int size : sizes) {
        cout << size << " ";
    }
    cout << endl;
    return 0;
}