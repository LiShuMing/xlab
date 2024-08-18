#include "../include/fwd.h"
class Solution {
public:
    int countNegatives(vector<vector<int>>& grid) {
        int count = 0;
        // use binary search to find the first negative number in each row
        for (int i = 0; i < grid.size(); i++) {
            int left = 0;
            int right = grid[i].size() - 1;
            while (left <= right) {
                int mid = left + (right - left) / 2;
                if (grid[i][mid] < 0) {
                    right = mid - 1;
                }
                else {
                    left = mid + 1;
                }
            }   
            if (left < grid[i].size()) {
                count += grid[i].size() - left;
            }
        }
        return count;
    }
};
int main() {
    Solution solution;
    vector<vector<int>> grid = {{4,3,2,-1},{3,2,1,-1},{1,1,-1,-2},{-1,-1,-2,-3}};
    cout << solution.countNegatives(grid) << endl;
    return 0;
}