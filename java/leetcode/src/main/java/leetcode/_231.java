package leetcode;

/**
 * @author shuming.lsm
 * @version 2019/12/03
 */
public class _231 {
    public boolean isPowerOfTwo(int n) {
        int v = 0, count = 0;
        n = Math.abs(n);
        for (int i = 0; i < 32; i++) {
            v = n & 1;
            if (v == 1) {
                count++;
            }
            n >>= 1;
        }
        if (count > 1) {
            return false;
        }
        return true;
    }
}
