#include "../include/fwd.h"

class Solution {
public:
    vector<vector<int>> combine(int n, int k) {
        vector<vector<int>> result;
        vector<int> path;
        backtrack(n, k, 1, path, result);
        return result;
    }
    void backtrack(int n, int k, int start, vector<int>& path, vector<vector<int>>& result) {
        if (path.size() == k) {
            result.push_back(path);
            return;
        }
        for (int i = start; i <= n; i++) {
            path.push_back(i);
            backtrack(n, k, i + 1, path, result);
            path.pop_back();
        }
    }
};