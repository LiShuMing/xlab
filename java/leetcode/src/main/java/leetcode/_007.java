package leetcode;

/**
 * @author shuming.lsm
 * @version 2019/12/03
 */
public class _007 {
    public int reverse(int x) {
        int  mod = 0, res = 0;
        while (x != 0) {
            mod = x % 10;
            x = x / 10;
            if (res > Integer.MAX_VALUE / 10 || (res == Integer.MAX_VALUE / 10 && mod > Integer.MAX_VALUE % 10)) {
                res = 0;
                break;
            }
            if (res < Integer.MIN_VALUE / 10 || (res == Integer.MIN_VALUE / 10 && mod < Integer.MIN_VALUE % 10)) {
                res = 0;
                break;
            }
            res = res * 10 + mod;
        }
        return res;
    }

    public static void main(String[] args) {
        System.out.println(new _007().reverse(-100));
    }
}
