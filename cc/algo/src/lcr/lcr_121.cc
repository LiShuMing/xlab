#include "../include/fwd.h"

class Solution {
    public:
        bool findTargetIn2DPlants(vector<vector<int>>& plants, int target) {
            if (plants.empty()) return false;
            int n = plants.size();
            int m = plants[0].size();
        
            int i = 0, j = m - 1;
            while (i < n && j >= 0) {
                if (plants[i][j] == target) {
                    return true;
                }
                if (plants[i][j] < target) {
                    i++;
                } else {
                    j--;
                }
            }
            return false;
        }
    };

int main() {
    Solution solution;
    vector<vector<int>> plants = {{1, 2, 3}, {4, 5, 6}, {7, 8, 9}};
    int target = 5;
    cout << solution.findTargetIn2DPlants(plants, target) << endl;
    return 0;
}