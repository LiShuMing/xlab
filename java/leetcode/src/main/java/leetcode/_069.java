package leetcode;

/**
 * @author shuming.lsm
 * @version 2019/12/23
 */
public class _069 {
    public int mySqrt(int x) {
        if (x <= 0) return 0;

        long left = 0, right = x / 2 + 1, mid = 0, square = 0;
        while (left < right) {
            mid = (left + right + 1) >>> 1;
            square = mid * mid;
            if (square > x) {
                right = mid - 1;
            } else {
                left = mid;
            }
        }
        return (int)left;
    }

    public static void main(String[] args) {
        int r = new _069().mySqrt(4);
        System.out.println(r);
    }
}
