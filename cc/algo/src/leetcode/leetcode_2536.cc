#include "../include/fwd.h"

class Solution {
    public:
        vector<vector<int>> rangeAddQueries(int n, vector<vector<int>>& queries) {
            vector<vector<int>> diff(n + 2, vector<int>(n + 2, 0));
            for (auto& query : queries) {
                int row1 = query[0];
                int col1 = query[1];
                int row2 = query[2];
                int col2 = query[3];
                diff[row1 + 1][col1 + 1]++;
                diff[row1 + 1][col2 + 2]--;
                diff[row2 + 2][col1 + 1]--;
                diff[row2 + 2][col2 + 2]++;
            }
           vector<vector<int>> ans(n, vector<int>(n, 0)); 
           for (int i = 0; i < n; i++) {
                for (int j = 0; j < n; j++) {
                    diff[i+1][j+1] += diff[i+1][j] + diff[i][j+1] - diff[i][j];
                    ans[i][j] = diff[i+1][j+1];
                }
           }
        //    for (auto& query : queries) {
        //        int row1 = query[0];
        //        int col1 = query[1];
        //        int row2 = query[2];
        //        int col2 = query[3];
        //        for (int i = row1; i <= row2; i++) {
        //         for (int j = col1; j <= col2; j++) {
        //             ans[i][j]++;
        //         }
        //        }
        //    }
           return ans;
        }
    };
int main() {
    Solution solution;
    int n = 3;
    vector<vector<int>> queries = {{0, 0, 2, 2}, {0, 0, 1, 1}};
    vector<vector<int>> ans = solution.rangeAddQueries(n, queries);
    for (auto& row : ans) {
        for (auto& val : row) {
            cout << val << " ";
        }
        cout << endl;
    }
    return 0;
}