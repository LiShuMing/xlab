#include "../include/fwd.h"

class Solution {
public:
    int numMagicSquaresInside(vector<vector<int>>& grid) {
        int ans = 0;
        int m = grid.size();
        int n = grid[0].size();
        if (m < 3 || n < 3) {
            return 0;
        }
        for (int i = 0; i < m - 2; i++) {
            for (int j = 0; j < n - 2; j++) {
                if (isMagicSquare(grid, i, j)) {
                    ans++;
                }
            }
        }
        return ans;
    }
    
    bool isMagicSquare(vector<vector<int>>& grid, int i, int j) {
        // Check uniqueness: must contain 1-9 exactly once
        int used = 0;
        for (int x = i; x < i + 3; x++) {
            for (int y = j; y < j + 3; y++) {
                int val = grid[x][y];
                // Must be between 1 and 9
                if (val < 1 || val > 9) {
                    return false;
                }
                // Must not be repeated
                int bit = 1 << val;
                if (used & bit) {
                    return false;
                }
                used |= bit;
            }
        }
        // Must have exactly 9 unique numbers (bits 1-9 set)
        if (used != 0x3FE) {  // Binary: 1111111110 (bits 1-9)
            return false;
        }
        
        // check the sum of the rows
        for (int x = i; x < i + 3; x++) {
            int sum = 0;
            for (int y = j; y < j + 3; y++) {
                sum += grid[x][y];
            }
            if (sum != 15) {
                return false;
            }
        }
        // check the sum of the columns
        for (int y = j; y < j + 3; y++) {
            int sum = 0;
            for (int x = i; x < i + 3; x++) {
                sum += grid[x][y];
            }
            if (sum != 15) {
                return false;
            }
        }
        // check the sum of the diagonals
        int sum = 0;
        for (int x = i, y = j + 2; x < i + 3; x++, y--) {
            sum += grid[x][y];
        }
        if (sum != 15) {
            return false;
        }

        // check the sum of the other diagonal
        sum = 0;
        for (int x = i, y = j; x < i + 3; x++, y++) {
            sum += grid[x][y];
        }
        if (sum != 15) {
            return false;
        }
        return true;
    }
};

int main() {
    Solution solution;
    int arr1[] = {4, 3, 8, 4};
    int arr2[] = {9, 5, 1, 9};
    int arr3[] = {2, 7, 6, 2};
    vector<vector<int>> grid;
    grid.push_back(vector<int>(arr1, arr1 + 4));
    grid.push_back(vector<int>(arr2, arr2 + 4));
    grid.push_back(vector<int>(arr3, arr3 + 4));
    cout << solution.numMagicSquaresInside(grid) << endl;
    return 0;
}
