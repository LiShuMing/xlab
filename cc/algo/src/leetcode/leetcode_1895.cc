#include "../include/fwd.h"

class Solution {
public:
    int largestMagicSquare(vector<vector<int> >& grid) {
        int m = grid.size();
        int n = grid[0].size();
        
        // Build prefix sum matrices
        // rowPrefix[i][j] = sum of row i from column 0 to j-1
        vector<vector<int> > rowPrefix(m, vector<int>(n + 1, 0));
        // colPrefix[i][j] = sum of column j from row 0 to i-1
        vector<vector<int> > colPrefix(m + 1, vector<int>(n, 0));
        // diag1Prefix[i][j] = sum of main diagonal ending at (i, j)
        vector<vector<int> > diag1Prefix(m, vector<int>(n, 0));
        // diag2Prefix[i][j] = sum of anti-diagonal starting at (i, j)
        vector<vector<int> > diag2Prefix(m, vector<int>(n, 0));
        
        for (int i = 0; i < m; i++) {
            for (int j = 0; j < n; j++) {
                // Row prefix
                rowPrefix[i][j + 1] = rowPrefix[i][j] + grid[i][j];
                
                // Column prefix
                colPrefix[i + 1][j] = colPrefix[i][j] + grid[i][j];
                
                // Main diagonal prefix
                diag1Prefix[i][j] = grid[i][j];
                if (i > 0 && j > 0) {
                    diag1Prefix[i][j] += diag1Prefix[i - 1][j - 1];
                }
                
                // Anti-diagonal prefix
                diag2Prefix[i][j] = grid[i][j];
                if (i > 0 && j + 1 < n) {
                    diag2Prefix[i][j] += diag2Prefix[i - 1][j + 1];
                }
            }
        }
        
        int ans = 0;
        for (int i = 0; i < m; i++) {
            for (int j = 0; j < n; j++) {
                // k can't exceed min(m-i, n-j)
                int maxK = min(m - i, n - j);
                for (int k = maxK; k > ans; k--) {
                    if (isMagicSquare(grid, rowPrefix, colPrefix, diag1Prefix, diag2Prefix, i, j, k)) {
                        ans = k;
                        break; // Found larger k, no need to check smaller
                    }
                }
            }
        }
        return ans;
    }
    
    // Helper to get row sum using prefix sum
    static int getRowSum(const vector<vector<int> >& rowPrefix, int i, int j, int k) {
        return rowPrefix[i][j + k] - rowPrefix[i][j];
    }
    
    // Helper to get column sum using prefix sum
    static int getColSum(const vector<vector<int> >& colPrefix, int i, int j, int k) {
        return colPrefix[i + k][j] - colPrefix[i][j];
    }
    
    // Helper to get main diagonal sum using prefix sum
    static int getMainDiagSum(const vector<vector<int> >& diag1Prefix, int i, int j, int k) {
        int x = i + k - 1;
        int y = j + k - 1;
        int sum = diag1Prefix[x][y];
        if (i > 0 && j > 0) {
            sum -= diag1Prefix[i - 1][j - 1];
        }
        return sum;
    }
    
    // Helper to get anti-diagonal sum using prefix sum
    static int getAntiDiagSum(const vector<vector<int> >& diag2Prefix, int i, int j, int k) {
        int x = i + k - 1;
        int sum = diag2Prefix[x][j];
        if (i > 0 && j + k < (int)diag2Prefix[0].size()) {
            sum -= diag2Prefix[i - 1][j + k];
        }
        return sum;
    }
    
    static bool isMagicSquare(vector<vector<int> >& grid,
                               const vector<vector<int> >& rowPrefix,
                               const vector<vector<int> >& colPrefix,
                               const vector<vector<int> >& diag1Prefix,
                               const vector<vector<int> >& diag2Prefix,
                               int i, int j, int k) {
        // Get target from first row using prefix sum
        int target = getRowSum(rowPrefix, i, j, k);
        
        // Check all rows
        for (int x = i; x < i + k; x++) {
            if (getRowSum(rowPrefix, x, j, k) != target) {
                return false;
            }
        }
        
        // Check all columns
        for (int y = j; y < j + k; y++) {
            if (getColSum(colPrefix, i, y, k) != target) {
                return false;
            }
        }
        
        // Check main diagonal
        if (getMainDiagSum(diag1Prefix, i, j, k) != target) {
            return false;
        }
        
        // Check anti-diagonal
        if (getAntiDiagSum(diag2Prefix, i, j, k) != target) {
            return false;
        }
        
        return true;
    }
};