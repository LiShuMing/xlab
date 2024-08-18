package leetcode;

import com.google.common.base.Joiner;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/**
 * @author shuming.lsm
 * @version 2020/04/26
 */
public class _051 {
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

    private void backtrace(int i, int n, List<Integer> list, List<List<String>> ret) {
        System.out.println("i=" + i);

        // OK
        if (list.size() == n) {
            List<String> r = new ArrayList<>();
            for (Integer l: list) {
                char[] rc = new char[n];
                Arrays.fill(rc, D);
                rc[l] = Q;
                r.add(new String(rc));
            }
            ret.add(r);
            return;
        }

        for (int j = i; j < n; j++) {
            if (!list.contains(j) && !alreadyHaveQueue(j, list)) {
                list.add(j);
                backtrace(j + 1, n, list, ret);
                list.remove(list.size() - 1);
            }
        }
    }

    public List<List<String>> solveNQueens(int n) {
        List<List<String>> ret = new ArrayList();
        List<Integer> list = new ArrayList<>();
        backtrace(0, n, list, ret);
        return ret;
    }

    public static void main(String[] args) {
        List<List<String>> ret = new _051().solveNQueens(4);
        for (List<String> l: ret) {
            String r = Joiner.on(",").join(l);
            System.out.println("RET:" + r);
        }
    }
}
