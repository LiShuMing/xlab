package leetcode;

import java.util.ArrayList;
import java.util.List;

/**
 * @author shuming.lsm
 * @version 2019/12/03
 */
public class _022 {
    public List<String> generateParenthesis(int n) {
        List<String> ret = new ArrayList<>();
        backtrace(ret, "", 0, 0, n);
        return ret;
    }

    private void backtrace(List<String> ret, String r, int left, int right, int n) {
        if (r.length() == 2 * n) {
            ret.add(r);
            return;
        }
        if (left < n) {
            backtrace(ret, r + "(", left + 1, right, n);
        }
        if (left > right) {
            backtrace(ret, r + ")", left, right + 1, n);
        }
    }

    public static void main(String[] args) {
        List<String> r = new _022().generateParenthesis(3);
        for (String s: r) {
            System.out.println(s);
        }
    }
}
