package leetcode;

/**
 * @author shuming.lsm
 * @version 2019/12/04
 */
public class _029 {
    public int divide(int dividend, int divisor) {
        boolean flag = (dividend > 0) ^ (divisor > 0);
        if (dividend > 0) {
            dividend = -dividend;
        }
        if (divisor > 0) {
            divisor = -divisor;
        }
        int r = 0;
        while (dividend <= divisor) {
            int d1 = divisor, m = -1;
            while (dividend <= d1 << 1) {
                if (d1 <= Integer.MIN_VALUE >> 1) break;
                m = m << 1;
                d1 = d1 << 1;
            }
            dividend = dividend - d1;
            r += m;
        }
        if (!flag) {
            if (r <= Integer.MIN_VALUE) return Integer.MAX_VALUE;
            r = -r;
        }
        return r;
    }
    public static void main(String[] args) {
        int r = new _029().divide(10,-3);
        System.out.println(r);
    }
}
