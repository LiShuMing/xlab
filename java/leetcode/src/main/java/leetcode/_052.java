package leetcode;

import com.google.common.base.Joiner;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/**
 * @author shuming.lsm
 * @version 2020/04/26
 */
public class _052 {
    private final static char Q = 'Q';
    private final static char D = '.';

    private boolean alreadyHaveQueue(int m, List<Integer> list) {
        int currentRow = list.size();
        for (int row = 0; row < list.size(); row++) {
            if (Math.abs(currentRow - row) == Math.abs(m - list.get(row))) {
                return true;
            }
        }
        return false;
    }

    private int backtrace(int n, List<Integer> list) {

        if (list.size() == n) {
            return 1;
        }

        int r = 0;
        for (int j = 0; j < n; j++) {
            if (!list.contains(j) && !alreadyHaveQueue(j, list)) {
                list.add(j);
                r += backtrace(n, list);
                list.remove(list.size() - 1);
            }
        }
        return r;
    }

    public int totalNQueens(int n) {
        List<Integer> list = new ArrayList<>();
        return backtrace(n, list);
    }

    public static void main(String[] args) {
        int ret = new _052().totalNQueens(4);
        System.out.println("ret:" + ret);
    }
}
