package leetcode.array;

/**
 * Created by lishuming on 2018/3/13.
 */
public class BattleShipsOnaBoard {
    public static void main(String[] args) throws Exception {
        char[][] board = {{'X', '.', '.', 'X'}, {'.', '.', '.', 'X'}, {'.', '.', '.', 'X'}};

        System.out.println(new BattleShipsOnaBoard().battleShipOnaBoard(board));
    }

    public int battleShipOnaBoard(char[][] board) {
        if (board.length <= 0) {
            return 0;
        }
        int count = 0;
        for (int i = 0; i < board.length; i++) {
            for (int j = 0; j < board[0].length; j++) {
                if (board[i][j] == 'X') {
                    if (i - 1 >= 0) {
                        if (board[i - 1][j] == 'X') {
                            continue;
                        }
                    }

                    if (j - 1 >= 0) {
                        if (board[i][j - 1] == 'X') {
                            continue;
                        }
                    }

                    count++;
                }
            }
        }

        return count;
    }
}
