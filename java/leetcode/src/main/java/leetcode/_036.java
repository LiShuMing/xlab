package leetcode;

/**
 * @author shuming.lsm
 * @version 2019/12/11
 */
public class _036 {
    private void initMap(int[] map) {
        for (int i = 0; i < map.length; i++) {
            map[i] = 0;
        }
    }
    public boolean isValidSudoku(char[][] board) {
        if (board == null) return false;

        int[] map = {0, 0, 0, 0, 0, 0, 0, 0, 0};
        for (int i = 0; i <  9; i++) {
            initMap(map);
            for (int j = 0; j < 9; j++) {
                if (map[j] == 1) {
                    return false;
                } else {
                    map[board[i][j]] = 1;
                }
            }
        }

        for (int i = 0; i <  9; i++) {
            initMap(map);
            for (int j = 0; j < 9; j++) {
                if (map[j] == 1) {
                    return false;
                } else {
                    map[board[j][i]] = 1;
                }
            }
        }

        for (int i = 0; i < 9; i++) {
            initMap(map);

            int m = i / 3;
            int n = i % 3;
            for (int j = 0; j < 9; j++) {
                int x = 3 * m + j / 3;
                int y = 3 * n + j % 3;
                int v = board[x][y];
                if (map[v] == 1) {
                    return false;
                } else {
                    map[v] = 1;
                }
            }
        }

        return true;
    }
}
