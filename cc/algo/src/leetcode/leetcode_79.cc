#include "../include/fwd.h"

class Solution {
public:
    bool exist(vector<vector<char>>& board, string word) {
        for (int i = 0; i < board.size(); i++) {
            for (int j = 0; j < board[0].size(); j++) {
                if (backtrack(board, word, i, j, 0)) return true;
            }
        }
        return false;
    }
    bool backtrack(vector<vector<char>>& board, string word, int i, int j, int k) {
        if (k == word.size()) return true;
        if (i < 0 || i >= board.size() || j < 0 || j >= board[0].size()) return false;
        if (board[i][j] != word[k]) return false;
        char temp = board[i][j];
        board[i][j] = '#';
        if (backtrack(board, word, i + 1, j, k + 1)) return true;
        if (backtrack(board, word, i - 1, j, k + 1)) return true;
        if (backtrack(board, word, i, j + 1, k + 1)) return true;
        if (backtrack(board, word, i, j - 1, k + 1)) return true;
        board[i][j] = temp;
        return false;
    }
};

int main() {
    Solution solution;
    vector<vector<char>> board = {{'A', 'B', 'C', 'E'}, {'S', 'F', 'C', 'S'}, {'A', 'D', 'E', 'E'}};
    vector<vector<char>> board = {{'A', 'B', 'C', 'E'}, {'S', 'F', 'C', 'S'}, {'A', 'D', 'E', 'E'}};
    string word = "ABCCED";
    cout << solution.exist(board, word) << endl;
    word = "SEE";
    cout << solution.exist(board, word) << endl;
    word = "ABCB";
    cout << solution.exist(board, word) << endl;
    return 0;
}