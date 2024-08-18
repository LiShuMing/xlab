#include "../include/fwd.h"

/**
 * LeetCode 52: Total N-Queens
 * 
 * Count the number of distinct ways to place n queens on an n×n chessboard
 * so that no two queens attack each other.
 * 
 * Approach: Backtracking with safety checks
 * - Only check columns and diagonals (rows are handled by recursion)
 * - Early termination when unsafe position found
 */
class Solution {
public:
    int totalNQueens(int n) {
        
        vector<vector<char>> board(n, vector<char>(n, '.'));
        int ans = 0;
        backtrack(board, 0, ans);
        return ans;
    }
    
    void backtrack(vector<vector<char>>& board, int row, int& ans) {
        if (row == board.size()) {
            ans++;
            return;
        }
        
        for (int col = 0; col < board[0].size(); col++) {
            if (isSafe(board, row, col)) {
                board[row][col] = 'Q';
                backtrack(board, row + 1, ans);
                board[row][col] = '.';
            }
        }
    }
    
    bool isSafe(vector<vector<char>>& board, int row, int col) {
        int n = board.size();
        
        // Check column (all rows above current)
        for (int i = 0; i < row; i++) {
            if (board[i][col] == 'Q') return false;
        }
        
        // Check upper-left diagonal: (row-1, col-1), (row-2, col-2), ...
        for (int i = 1; i <= row; i++) {
            if (col - i >= 0 && board[row - i][col - i] == 'Q') return false;
        }
        
        // Check upper-right diagonal: (row-1, col+1), (row-2, col+2), ...
        for (int i = 1; i <= row; i++) {
            if (col + i < n && board[row - i][col + i] == 'Q') return false;
        }
        
        return true;
    }
};

int main() {
    Solution solution;
    int n = 4;
    cout << "n=" << n << ": " << solution.totalNQueens(n) << endl;  // Expected: 2
    
    // Test additional cases
    n = 1;
    cout << "n=" << n << ": " << solution.totalNQueens(n) << endl;  // Expected: 1
    
    n = 2;
    cout << "n=" << n << ": " << solution.totalNQueens(n) << endl;  // Expected: 0
    
    n = 3;
    cout << "n=" << n << ": " << solution.totalNQueens(n) << endl;  // Expected: 0
    
    n = 8;
    cout << "n=" << n << ": " << solution.totalNQueens(n) << endl;  // Expected: 92
    
    return 0;
}
