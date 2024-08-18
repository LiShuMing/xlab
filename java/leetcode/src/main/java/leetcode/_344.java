package leetcode;

/**
 * @author shuming.lsm
 * @version 2019/12/14
 */
public class _344 {
    public void reverseString(char[] s) {
        if (s == null || s.length == 0) return;

        char t;
        int p = 0, q = s.length - 1;
        while (p < q) {
            t = s[p];
            s[p++] = s[q];
            s[q--] = t;
        }
    }
}
